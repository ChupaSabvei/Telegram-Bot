from __future__ import annotations

import json
from dataclasses import dataclass

from openai import AsyncOpenAI

from src.ai.prompts import SYSTEM_PROMPT, build_user_prompt


@dataclass(slots=True)
class LLMResponse:
    event_ids: list[str]
    clarification_needed: bool
    clarification_message: str | None


class OpenAIClient:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self.model = model
        self.client = AsyncOpenAI(api_key=api_key)

    async def rank(self, query: str, candidates: list[dict]) -> LLMResponse:
        payload = build_user_prompt(query=query, candidates_json=json.dumps(candidates, ensure_ascii=False))
        response = await self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": payload},
            ],
            timeout=8,
        )

        text = getattr(response, "output_text", "") or "{}"
        data = json.loads(text)
        return LLMResponse(
            event_ids=[str(item) for item in data.get("event_ids", [])],
            clarification_needed=bool(data.get("clarification_needed", False)),
            clarification_message=data.get("clarification_message"),
        )
