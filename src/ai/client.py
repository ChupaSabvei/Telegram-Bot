from __future__ import annotations

import json
import re
from dataclasses import dataclass

from openai import AsyncOpenAI

from src.ai.prompts import PLACES_SYSTEM_PROMPT, SYSTEM_PROMPT, build_places_prompt, build_user_prompt


@dataclass(slots=True)
class LLMResponse:
    event_ids: list[str]
    clarification_needed: bool
    clarification_message: str | None


def _parse_llm_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


class OpenAIClient:
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
    ) -> None:
        self.model = model
        kwargs: dict[str, str] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = AsyncOpenAI(**kwargs)

    async def rank(self, query: str, candidates: list[dict]) -> LLMResponse:
        payload = build_user_prompt(
            query=query,
            candidates_json=json.dumps(candidates, ensure_ascii=False),
        )
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": payload},
            ],
            temperature=0.2,
            timeout=8,
        )

        text = response.choices[0].message.content or "{}"
        data = _parse_llm_json(text)
        return LLMResponse(
            event_ids=[str(item) for item in data.get("event_ids", [])],
            clarification_needed=bool(data.get("clarification_needed", False)),
            clarification_message=data.get("clarification_message"),
        )

    async def recommend_places(self, query: str, city_name: str, topic: str) -> dict:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": PLACES_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_places_prompt(
                        query=query,
                        city_name=city_name,
                        topic=topic,
                    ),
                },
            ],
            temperature=0.4,
            timeout=10,
        )
        text = response.choices[0].message.content or "{}"
        return _parse_llm_json(text)
