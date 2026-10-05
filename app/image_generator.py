import io
import logging
import math
import os
import textwrap
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import requests

from app.models import Panel

logger = logging.getLogger(__name__)

# ── Mood → gradient color pairs ───────────────────────────────────────────────
MOOD_COLORS: dict[str, tuple[tuple, tuple]] = {
    "excited":    ((255, 210, 0),   (230, 90, 0)),
    "sad":        ((80,  130, 220), (20,  50, 140)),
    "tense":      ((200, 20,  50),  (80,  0,  20)),
    "peaceful":   ((100, 210, 160), (40,  140, 100)),
    "mysterious": ((110, 30,  200), (40,  0,   90)),
    "humorous":   ((255, 200, 80),  (200, 130, 30)),
    "dramatic":   ((60,  60,  70),  (10,  10,  15)),
    "neutral":    ((110, 110, 160), (50,  50,  100)),
}

ART_STYLE_LABELS: dict[str, str] = {
    "manga":      "MANGA",
    "superhero":  "SUPERHERO",
    "watercolor": "WATERCOLOR",
    "noir":       "NOIR",
    "cartoon":    "CARTOON",
    "retro":      "RETRO",
    "anime":      "ANIME",
    "sketch":     "SKETCH",
}


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Try common Windows system fonts; fall back to PIL default."""
    candidates = [
        ("Impact.ttf",        True),
        ("arialbd.ttf",       bold),
        ("arial.ttf",         not bold),
        ("DejaVuSans-Bold.ttf", bold),
        ("DejaVuSans.ttf",    not bold),
    ]
    for name, _preferred in candidates:
        try:
            return ImageFont.truetype(name, size)
        except (IOError, OSError):
            pass
    return ImageFont.load_default()


class PanelImageGenerator:
    """
    Generates panel images via Imagen 3 (Google AI).
    Falls back to a rich PIL-rendered placeholder on any API error.
    """

    IMAGEN_MODEL = "imagen-3.0-generate-002"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY", "")
        self._client = None  # lazily initialized

    # ── Public API ────────────────────────────────────────────────────────────

    def generate_panel_image(
        self,
        panel: Panel,
        art_style: str,
        color_palette: str,
        output_dir: str,
        width: int = 768,
        height: int = 768,
        filename: Optional[str] = None,
    ) -> str:
        """
        Generate (or render) a panel image and save it to *output_dir*.
        Returns the absolute path of the saved file.
        """
        fname = filename or f"panel_{panel.panel_number:02d}_{panel.id}.png"
        out_path = Path(output_dir) / fname

        # 1. Try Imagen 3 first if Google API key is configured
        if self.api_key and "your_" not in self.api_key:
            try:
                img = self._generate_with_imagen(panel, art_style, color_palette)
                if img is not None:
                    img = img.resize((width, height), Image.LANCZOS)
                    img.save(str(out_path), "PNG", optimize=True)
                    logger.info("Imagen 3 generated panel %d", panel.panel_number)
                    return str(out_path)
            except Exception as exc:
                logger.warning(
                    "Imagen 3 failed for panel %d (%s). Checking Hugging Face / fallback...",
                    panel.panel_number,
                    exc,
                )

        # 2. Try Hugging Face if HF_API_KEY is configured
        try:
            img = self._generate_with_huggingface(panel, art_style, color_palette)
            if img is not None:
                img = img.resize((width, height), Image.LANCZOS)
                img.save(str(out_path), "PNG", optimize=True)
                logger.info("Hugging Face generated panel %d", panel.panel_number)
                return str(out_path)
        except Exception as exc:
            logger.warning("Hugging Face generation failed: %s", exc)

        # 3. PIL fallback
        img = self._create_placeholder(panel, art_style, width, height)
        img.save(str(out_path), "PNG", optimize=True)
        logger.info("PIL placeholder created for panel %d", panel.panel_number)
        return str(out_path)

    # ── Imagen 3 generation ───────────────────────────────────────────────────

    def _get_client(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _build_imagen_prompt(self, panel: Panel, art_style: str, color_palette: str) -> str:
        from app.gemini_flash import STYLE_PROMPTS
        style_desc = STYLE_PROMPTS.get(art_style, "comic book art")
        return (
            f"{panel.description}. "
            f"Art style: {style_desc}. "
            f"Color palette: {color_palette}. "
            f"Comic book panel composition. "
            f"High quality, detailed illustration. "
            f"No text, no speech bubbles, no captions in the image."
        )

    def _generate_with_imagen(
        self, panel: Panel, art_style: str, color_palette: str
    ) -> Optional[Image.Image]:
        from google.genai import types
        client = self._get_client()
        prompt = self._build_imagen_prompt(panel, art_style, color_palette)

        response = client.models.generate_images(
            model=self.IMAGEN_MODEL,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="1:1",
                safety_filter_level="BLOCK_MEDIUM_AND_ABOVE",
                person_generation="ALLOW_ADULT",
            ),
        )

        for generated in response.generated_images:
            image_bytes = generated.image.image_bytes
            return Image.open(io.BytesIO(image_bytes)).convert("RGB")

        return None

    # ── Hugging Face generation ───────────────────────────────────────────────

    def _generate_with_huggingface(
        self, panel: Panel, art_style: str, color_palette: str
    ) -> Optional[Image.Image]:
        """Generate panel illustration using Hugging Face InferenceClient."""
        hf_token = os.getenv("HF_API_KEY") or os.getenv("HUGGINGFACE_API_KEY")
        if not hf_token or "your_" in hf_token:
            return None

        model_id = os.getenv(
            "HF_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell"
        )
        prompt = self._build_imagen_prompt(panel, art_style, color_palette)

        try:
            from huggingface_hub import InferenceClient
            client = InferenceClient(token=hf_token)
            img = client.text_to_image(prompt, model=model_id)
            if img:
                return img.convert("RGB")
        except Exception as exc:
            logger.warning("Hugging Face InferenceClient failed: %s", exc)

        return None

    # ── PIL placeholder ───────────────────────────────────────────────────────

    def _create_placeholder(
        self, panel: Panel, art_style: str, width: int, height: int
    ) -> Image.Image:
        """Create a visually rich placeholder panel using only PIL."""
        top_color, bot_color = MOOD_COLORS.get(panel.mood, MOOD_COLORS["neutral"])

        # ── Gradient background ───────────────────────────────────────────────
        img = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(img)

        for y in range(height):
            t = y / height
            r = int(top_color[0] * (1 - t) + bot_color[0] * t)
            g = int(top_color[1] * (1 - t) + bot_color[1] * t)
            b = int(top_color[2] * (1 - t) + bot_color[2] * t)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # ── Halftone dot texture ──────────────────────────────────────────────
        spacing = 28
        dot_r   = 4
        for gx in range(0, width + spacing, spacing):
            for gy in range(0, height + spacing, spacing):
                offset = spacing // 2 if ((gx // spacing) % 2) else 0
                cx, cy = gx, gy + offset
                draw.ellipse(
                    [cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r],
                    fill=(255, 255, 255, 25)
                )

        # ── Diagonal accent lines ─────────────────────────────────────────────
        line_color = (255, 255, 255, 15)
        for x in range(-height, width, 60):
            draw.line([(x, 0), (x + height, height)], fill=line_color, width=2)

        # ── Panel border ──────────────────────────────────────────────────────
        bw = 6
        draw.rectangle([bw, bw, width - bw, height - bw],
                       outline=(0, 0, 0), width=bw)
        draw.rectangle([bw + 4, bw + 4, width - bw - 4, height - bw - 4],
                       outline=(255, 255, 255, 60), width=1)

        # ── Art style badge (top-left) ────────────────────────────────────────
        label     = ART_STYLE_LABELS.get(art_style, art_style.upper())
        badge_fnt = _load_font(max(14, width // 40), bold=True)
        bbox      = badge_fnt.getbbox(label)
        bw2, bh2  = bbox[2] - bbox[0] + 20, bbox[3] - bbox[1] + 12
        draw.rectangle([16, 16, 16 + bw2, 16 + bh2], fill=(0, 0, 0, 200))
        draw.text((26, 20), label, fill=(255, 220, 0), font=badge_fnt)

        # ── Panel number badge (top-right) ────────────────────────────────────
        num_fnt  = _load_font(max(22, width // 22), bold=True)
        num_text = str(panel.panel_number)
        nbbox    = num_fnt.getbbox(num_text)
        nw, nh   = nbbox[2] - nbbox[0] + 24, nbbox[3] - nbbox[1] + 24
        nx       = width - nw - 16
        draw.rectangle([nx, 16, nx + nw, 16 + nh], fill=(255, 220, 0))
        draw.rectangle([nx, 16, nx + nw, 16 + nh], outline=(0, 0, 0), width=3)
        draw.text((nx + 12, 22), num_text, fill=(0, 0, 0), font=num_fnt)

        # ── Scene description text ────────────────────────────────────────────
        margin   = 20
        text_y   = height // 3
        box_h    = height - text_y - margin
        draw.rectangle(
            [margin, text_y, width - margin, height - margin],
            fill=(0, 0, 0, 190)
        )

        body_fnt = _load_font(max(13, width // 38))
        max_chars = (width - margin * 2 - 20) // max(1, (width // 38) // 2 + 1)
        wrapped  = textwrap.wrap(panel.description, width=max_chars)
        ty       = text_y + 14
        line_h   = max(16, width // 36)

        for line in wrapped[:10]:   # cap at 10 lines
            if ty + line_h > height - margin - 10:
                break
            draw.text((margin + 10, ty), line, fill=(240, 240, 240), font=body_fnt)
            ty += line_h

        # Mood label at bottom
        mood_fnt = _load_font(max(11, width // 48), bold=True)
        draw.text(
            (margin + 10, height - margin - 22),
            panel.mood.upper(),
            fill=(255, 220, 0, 180),
            font=mood_fnt,
        )

        return img
