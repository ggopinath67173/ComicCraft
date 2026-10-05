from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

try:
    from google import genai
except ImportError:
    genai = None

from app.models import ComicScript, Panel

logger = logging.getLogger(__name__)

STYLE_PROMPTS: dict[str, str] = {
    "manga": "Japanese manga style, detailed ink linework, screen tones, dynamic angles",
    "superhero": "Modern Western superhero comic book, bold inking, dramatic lighting, heroic poses",
    "watercolor": "Lush watercolor illustration, painterly textures, soft atmospheric washes",
    "noir": "Moody graphic novel noir, heavy shadow chiaroscuro, cinematic high-contrast lighting",
    "cartoon": "Lively Western cartoon animation style, expressive shapes, vibrant clean colors",
    "retro": "Vintage 1960s silver-age comic book art, halftone dot print, distressed paper tone",
    "anime": "Modern vibrant anime style, sharp cel-shaded highlights, cinematic aesthetic",
    "sketch": "Expressive pencil and charcoal concept sketch, cross-hatching, raw linework",
}


class StoryGenerator:
    """Generates structured comic scripts using Gemini 2.5 Flash."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY", "")
        self.model_name = os.getenv("GEMINI_FLASH_MODEL") or os.getenv("GEMINI_OUTLINE_MODEL", "gemini-3.5-flash-lite")
        self.client = None
        if genai and self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning("Could not initialize Google GenAI Client: %s", e)

    def generate_script(
        self,
        prompt: str,
        genre: str = "adventure",
        panel_count: int = 4,
        art_style: str = "manga",
        characters: str = "",
    ) -> ComicScript:
        """Generate a complete comic script using Gemini Flash, with robust fallback."""
        if not self.client and genai and self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning("Failed to initialize genai client: %s", e)

        if not self.client:
            logger.info("No active genai client; using fallback script.")
            return self._fallback_script(prompt, genre, art_style, panel_count)

        system_instruction = f"""
You are a master comic book writer and visual director.
Convert the user's idea into a complete {panel_count}-panel comic strip.
Genre: {genre}
Art Style: {art_style}
Characters: {characters if characters else 'infer from prompt'}

Respond with ONLY valid JSON matching this schema:
{{
  "title": "Comic Title",
  "logline": "One-sentence logline",
  "color_palette": "3-4 primary color accents, e.g. deep crimson, midnight blue, electric gold",
  "panels": [
    {{
      "panel_number": 1,
      "description": "Visual scene description describing character action, angle, lighting and composition",
      "speaker": "Name of character speaking or empty string",
      "dialogue": "Short snappy line of dialogue or empty string",
      "caption": "Narrative caption box text or empty string",
      "mood": "One of: excited, tense, sad, peaceful, mysterious, humorous, dramatic, neutral",
      "characters": ["Character Name"]
    }}
  ]
}}

Requirements:
- Exactly {panel_count} panels numbered 1 through {panel_count}.
- Strong narrative arc across the panels: setup, conflict/action, twist/climax, resolution.
- Keep descriptions visually concrete for an illustrator.
- Do NOT wrap in markdown formatting other than optional json code fences.
"""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=f"User story idea: {prompt}\n\nPlease generate a {panel_count}-panel comic script.",
                config={"system_instruction": system_instruction},
            )
            raw_text = response.text or ""
            return self._parse_response(raw_text, genre, art_style)
        except Exception as exc:
            logger.error("Gemini Flash generation failed: %s; using fallback.", exc)
            return self._fallback_script(prompt, genre, art_style, panel_count)

    def _parse_response(self, raw: str, genre: str, art_style: str) -> ComicScript:
        """Parse JSON response from Gemini into a ComicScript object."""
        cleaned = raw.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        data = json.loads(cleaned)

        title = data.get("title", "Untitled Comic")
        logline = data.get("logline", "")
        color_palette = data.get("color_palette", "vibrant comic tones")

        panels = []
        for item in data.get("panels", []):
            panel = Panel(
                panel_number=int(item.get("panel_number", len(panels) + 1)),
                description=item.get("description", ""),
                speaker=item.get("speaker", ""),
                dialogue=item.get("dialogue", ""),
                caption=item.get("caption", ""),
                mood=item.get("mood", "neutral").lower(),
                characters=item.get("characters", []),
            )
            panels.append(panel)

        return ComicScript(
            title=title,
            logline=logline,
            genre=genre,
            art_style=art_style,
            color_palette=color_palette,
            panels=panels,
        )

    def _fallback_script(
        self, prompt: str, genre: str, art_style: str, panel_count: int
    ) -> ComicScript:
        """Provide a fallback script when AI generation is unavailable."""
        title = prompt.split(".")[0][:40].strip() or "The Unwritten Tale"
        moods = ["mysterious", "tense", "excited", "dramatic", "humorous", "peaceful"]

        panels = []
        for i in range(1, panel_count + 1):
            mood = moods[(i - 1) % len(moods)]
            panels.append(
                Panel(
                    panel_number=i,
                    description=f"Panel {i}: A vivid {art_style} scene depicting {prompt} - Stage {i} of the journey.",
                    speaker="Protagonist" if i % 2 == 1 else "",
                    dialogue=f"We must move forward to panel {i}!" if i % 2 == 1 else "",
                    caption=f"Part {i} — The adventure unfolds under a dramatic sky.",
                    mood=mood,
                    characters=["Protagonist"],
                )
            )

        return ComicScript(
            title=title,
            logline=prompt,
            genre=genre,
            art_style=art_style,
            color_palette="midnight blue, neon purple, ember amber",
            panels=panels,
        )