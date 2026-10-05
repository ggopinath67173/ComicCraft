from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from app.models import ComicPage, Panel

logger = logging.getLogger(__name__)


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load a system font or fall back to default PIL font."""
    font_names = [
        "Impact.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "SegoeUI.ttf",
    ]
    for fn in font_names:
        try:
            return ImageFont.truetype(fn, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


class ComicLayoutBuilder:
    """
    Assembles multiple panel images into a unified, high-resolution comic strip / page.
    Supports classic (2-column grid), strip (linear), story (multi-row), and feature layouts.
    """

    CANVAS_WIDTH = 1800
    CANVAS_PADDING = 50
    PANEL_GAP = 30
    HEADER_HEIGHT = 160
    BG_COLOR = (17, 24, 39)        # Rich dark slate (#111827)
    BORDER_COLOR = (99, 102, 241)   # Indigo accent (#6366f1)
    CARD_BG = (31, 41, 55)          # Dark surface (#1f2937)

    def build(self, comic: ComicPage, output_dir: str) -> str:
        """
        Assemble the comic panels into a single image.
        Returns the absolute filepath to the generated assembled.png.
        """
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        dest_path = out_dir / "assembled.png"

        script = comic.script
        panels = script.panels if script and script.panels else []
        n_panels = max(len(panels), 1)
        template = (comic.layout_template or "classic").lower()

        # Compute panel layout slots (x, y, w, h)
        slots, canvas_w, canvas_h = self._calculate_slots(n_panels, template)

        # Create canvas
        canvas = Image.new("RGBA", (canvas_w, canvas_h), self.BG_COLOR)
        draw = ImageDraw.Draw(canvas)

        # Draw Title Banner
        self._draw_header(draw, script, canvas_w)

        # Place panels
        for i, slot in enumerate(slots):
            panel = panels[i] if i < len(panels) else None
            x, y, w, h = slot
            panel_img = self._load_or_create_panel_image(panel, i + 1, w, h)

            # Paste image
            canvas.paste(panel_img, (x, y))

            # Draw panel outline border
            draw.rectangle([x, y, x + w, y + h], outline=self.BORDER_COLOR, width=4)

            # Draw badge: Panel number
            self._draw_panel_badge(draw, x, y, i + 1)

            # Draw caption overlay if exists
            if panel and panel.caption:
                self._draw_caption_box(draw, x, y + h, w, panel.caption)

        # Save assembled image
        final_image = canvas.convert("RGB")
        final_image.save(dest_path, format="PNG", quality=95)
        logger.info("Assembled comic page saved to %s", dest_path)
        return str(dest_path)

    def _calculate_slots(
        self, n: int, template: str
    ) -> tuple[list[tuple[int, int, int, int]], int, int]:
        """Compute pixel bounds (x, y, w, h) for each panel slot."""
        usable_w = self.CANVAS_WIDTH - (2 * self.CANVAS_PADDING)
        start_y = self.HEADER_HEIGHT + self.CANVAS_PADDING

        slots = []

        if template == "strip" or n <= 2:
            # Linear horizontal or stacked strip
            if n <= 3:
                cols = n
                panel_w = int((usable_w - (cols - 1) * self.PANEL_GAP) / cols)
                panel_h = int(panel_w * 1.0)
                canvas_h = start_y + panel_h + self.CANVAS_PADDING
                for i in range(n):
                    x = self.CANVAS_PADDING + i * (panel_w + self.PANEL_GAP)
                    y = start_y
                    slots.append((x, y, panel_w, panel_h))
            else:
                # Vertical strip
                panel_w = usable_w
                panel_h = int(panel_w * 0.55)
                canvas_h = start_y + n * (panel_h + self.PANEL_GAP) + self.CANVAS_PADDING
                for i in range(n):
                    x = self.CANVAS_PADDING
                    y = start_y + i * (panel_h + self.PANEL_GAP)
                    slots.append((x, y, panel_w, panel_h))

        elif template == "feature" and n >= 3:
            # Hero panel (large) on top, remaining in a row underneath
            hero_w = usable_w
            hero_h = int(usable_w * 0.52)
            slots.append((self.CANVAS_PADDING, start_y, hero_w, hero_h))

            remaining = n - 1
            sub_w = int((usable_w - (remaining - 1) * self.PANEL_GAP) / remaining)
            sub_h = int(sub_w * 0.85)
            sub_y = start_y + hero_h + self.PANEL_GAP

            for i in range(remaining):
                x = self.CANVAS_PADDING + i * (sub_w + self.PANEL_GAP)
                slots.append((x, sub_y, sub_w, sub_h))

            canvas_h = sub_y + sub_h + self.CANVAS_PADDING

        else:
            # Classic / Story grid (2 columns standard)
            cols = 2 if n <= 6 else 3
            rows = math.ceil(n / cols)
            panel_w = int((usable_w - (cols - 1) * self.PANEL_GAP) / cols)
            panel_h = int(panel_w * 0.85)

            for i in range(n):
                r = i // cols
                c = i % cols
                x = self.CANVAS_PADDING + c * (panel_w + self.PANEL_GAP)
                y = start_y + r * (panel_h + self.PANEL_GAP)
                slots.append((x, y, panel_w, panel_h))

            canvas_h = start_y + rows * (panel_h + self.PANEL_GAP) + self.CANVAS_PADDING

        return slots, self.CANVAS_WIDTH, canvas_h

    def _draw_header(self, draw: ImageDraw.ImageDraw, script: Optional[Any], width: int):
        """Render stylish comic title header."""
        title = script.title if script and script.title else "ComicCraft AI"
        logline = script.logline if script and script.logline else ""

        title_font = _get_font(52, bold=True)
        sub_font = _get_font(22, bold=False)

        # Title text centered
        bbox = draw.textbbox((0, 0), title, font=title_font)
        tw = bbox[2] - bbox[0]
        tx = (width - tw) // 2
        ty = 36
        draw.text((tx, ty), title, fill=(243, 244, 246), font=title_font)

        # Subtitle / Logline
        if logline:
            disp_sub = logline[:90] + ("..." if len(logline) > 90 else "")
            sbbox = draw.textbbox((0, 0), disp_sub, font=sub_font)
            sw = sbbox[2] - sbbox[0]
            sx = (width - sw) // 2
            draw.text((sx, ty + 68), disp_sub, fill=(156, 163, 175), font=sub_font)

        # Decorative separator rule
        rule_y = self.HEADER_HEIGHT + 15
        draw.line(
            [(self.CANVAS_PADDING, rule_y), (width - self.CANVAS_PADDING, rule_y)],
            fill=(75, 85, 99),
            width=2,
        )

    def _draw_panel_badge(self, draw: ImageDraw.ImageDraw, x: int, y: int, num: int):
        """Draw a distinct numbered badge in the top-left of the panel."""
        badge_w, badge_h = 50, 42
        draw.rectangle(
            [x, y, x + badge_w, y + badge_h],
            fill=(17, 24, 39, 230),
            outline=self.BORDER_COLOR,
            width=2,
        )
        font = _get_font(20, bold=True)
        text = str(num)
        bbox = draw.textbbox((0, 0), text, font=font)
        tx = x + (badge_w - (bbox[2] - bbox[0])) // 2
        ty = y + (badge_h - (bbox[3] - bbox[1])) // 2
        draw.text((tx, ty), text, fill=(255, 255, 255), font=font)

    def _draw_caption_box(
        self, draw: ImageDraw.ImageDraw, x: int, bottom_y: int, w: int, caption: str
    ):
        """Draw comic narration box at bottom of panel."""
        if not caption.strip():
            return
        box_h = 44
        y = bottom_y - box_h
        draw.rectangle([x, y, x + w, bottom_y], fill=(15, 23, 42, 220))
        draw.line([(x, y), (x + w, y)], fill=(99, 102, 241), width=1)

        font = _get_font(18, bold=False)
        text = caption[:60] + ("..." if len(caption) > 60 else "")
        draw.text((x + 16, y + 12), text, fill=(241, 245, 249), font=font)

    def _load_or_create_panel_image(
        self, panel: Optional[Panel], num: int, width: int, height: int
    ) -> Image.Image:
        """Load the panel image or generate a fallback graphic that fits width/height."""
        if panel and panel.image_path and Path(panel.image_path).exists():
            try:
                img = Image.open(panel.image_path)
                return self._crop_and_resize(img, width, height)
            except Exception as e:
                logger.warning("Failed to open %s: %s", panel.image_path, e)

        # Fallback panel placeholder
        placeholder = Image.new("RGB", (width, height), self.CARD_BG)
        pdraw = ImageDraw.Draw(placeholder)
        font = _get_font(28, bold=True)
        desc_font = _get_font(18, bold=False)

        title = f"Panel {num}"
        pdraw.text((width // 2 - 50, height // 2 - 40), title, fill=(229, 231, 235), font=font)

        if panel and panel.description:
            summary = panel.description[:50] + ("..." if len(panel.description) > 50 else "")
            pdraw.text((40, height // 2 + 10), summary, fill=(156, 163, 175), font=desc_font)

        return placeholder

    @staticmethod
    def _crop_and_resize(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
        """Center-crop and resize image to exact dimensions."""
        img = img.convert("RGBA")
        src_w, src_h = img.size
        src_aspect = src_w / src_h
        target_aspect = target_w / target_h

        if src_aspect > target_aspect:
            # Source is wider: crop sides
            new_w = int(src_h * target_aspect)
            left = (src_w - new_w) // 2
            img = img.crop((left, 0, left + new_w, src_h))
        else:
            # Source is taller: crop top/bottom
            new_h = int(src_w / target_aspect)
            top = (src_h - new_h) // 2
            img = img.crop((0, top, src_w, top + new_h))

        return img.resize((target_w, target_h), Image.Resampling.LANCZOS)