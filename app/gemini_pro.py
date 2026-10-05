from __future__ import annotations

import logging
import os
from typing import Optional

from app.gemini_flash import StoryGenerator
from app.models import ComicScript

logger = logging.getLogger(__name__)


class QualityGenerator(StoryGenerator):
    """
    High-fidelity story generator using Gemini 2.5 Pro.
    Generates richer narrative pacing, character beats, and detailed visual framing.
    """

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key=api_key)
        self.model_name = os.getenv("GEMINI_PRO_MODEL", "gemini-2.5-pro")

    def generate_script(
        self,
        prompt: str,
        genre: str = "adventure",
        panel_count: int = 4,
        art_style: str = "manga",
        characters: str = "",
    ) -> ComicScript:
        logger.info(
            "Generating high-quality script with %s (panels=%d, genre=%s)",
            self.model_name,
            panel_count,
            genre,
        )
        return super().generate_script(
            prompt=prompt,
            genre=genre,
            panel_count=panel_count,
            art_style=art_style,
            characters=characters,
        )