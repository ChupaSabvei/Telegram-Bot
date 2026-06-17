from __future__ import annotations

import json
import re
from dataclasses import dataclass

from src.ai.client import OpenAIClient
from src.storage.schemas import ACTIVITY_SLUGS, ActivitySlug, EventDTO

CLASSIFY_SYSTEM = (
    "You classify events into exactly one activity category for a leisure survey. "
    f"Reply JSON only: {{\"activity_slug\": one of {list(ACTIVITY_SLUGS)}}}"
)


@dataclass(slots=True)
class ActivityClassifier:
    client: OpenAIClient | None

    async def classify(self, dto: EventDTO) -> ActivitySlug | None:
        if self.client is None:
            return None
        prompt = (
            f"Title: {dto.title}\n"
            f"Description: {dto.description or '—'}\n"
            f"Source: {dto.source_slug}\n"
            f"City: {dto.city_slug}\n"
            f"Category: {dto.category_slug}"
        )
        try:
            response = await self.client.client.chat.completions.create(
                model=self.client.model,
                messages=[
                    {"role": "system", "content": CLASSIFY_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                timeout=8,
            )
            text = response.choices[0].message.content or "{}"
            if text.strip().startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text.strip())
                text = re.sub(r"\s*```$", "", text)
            data = json.loads(text)
            slug = data.get("activity_slug")
            if slug in ACTIVITY_SLUGS:
                return slug  # type: ignore[return-value]
        except Exception:
            return None
        return None
