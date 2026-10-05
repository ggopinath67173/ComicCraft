import io
import logging
import zipfile
from pathlib import Path
from typing import Optional

from PIL import Image
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Spacer
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from app.models import ComicPage, ExportConfig

logger = logging.getLogger(__name__)


class ComicExporter:
    """
    Exports assembled comic pages to PDF or PNG.
    PDF embeds the assembled image with metadata; PNG saves directly.
    """

    # ── Public API ────────────────────────────────────────────────────────────

    def export_pdf(
        self,
        comic: ComicPage,
        output_path: str,
        config: Optional[ExportConfig] = None,
    ) -> str:
        """Export comic to a styled PDF. Returns path."""
        config = config or ExportConfig()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=1.5 * cm,
            leftMargin=1.5 * cm,
            topMargin=2 * cm,
            bottomMargin=1.5 * cm,
        )

        story_elements = []
        styles = getSampleStyleSheet()

        # ── Title ─────────────────────────────────────────────────────────────
        title_style = ParagraphStyle(
            "ComicTitle",
            parent=styles["Title"],
            fontSize=28,
            leading=34,
            textColor=colors.HexColor("#7c3aed"),
            spaceAfter=6,
            alignment=TA_CENTER,
        )
        sub_style = ParagraphStyle(
            "Logline",
            parent=styles["Normal"],
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#6b7280"),
            spaceAfter=10,
            alignment=TA_CENTER,
        )

        script = comic.script
        title   = script.title if script else "Comic"
        logline = script.logline if script else ""

        story_elements.append(Paragraph(title, title_style))
        if logline:
            story_elements.append(Paragraph(f"<i>{logline}</i>", sub_style))
        story_elements.append(HRFlowable(
            width="100%", thickness=2, color=colors.HexColor("#7c3aed"), spaceAfter=12
        ))

        # ── Assembled page image ───────────────────────────────────────────────
        if comic.assembled_image_path and Path(comic.assembled_image_path).exists():
            available_w = A4[0] - 3 * cm
            available_h = A4[1] - 8 * cm

            pil_img = Image.open(comic.assembled_image_path)
            iw, ih  = pil_img.size
            scale   = min(available_w / iw, available_h / ih)
            disp_w  = iw * scale
            disp_h  = ih * scale

            rl_img = RLImage(comic.assembled_image_path, width=disp_w, height=disp_h)
            story_elements.append(rl_img)
        else:
            story_elements.append(Paragraph("(No assembled image found)", sub_style))

        story_elements.append(Spacer(1, 0.5 * cm))

        # ── Panel script table ────────────────────────────────────────────────
        if config.include_captions and script and script.panels:
            panel_style = ParagraphStyle(
                "PanelDesc",
                parent=styles["Normal"],
                fontSize=9,
                leading=12,
                textColor=colors.HexColor("#374151"),
                spaceAfter=4,
            )
            label_style = ParagraphStyle(
                "PanelLabel",
                parent=styles["Normal"],
                fontSize=10,
                leading=13,
                textColor=colors.HexColor("#7c3aed"),
                fontName="Helvetica-Bold",
                spaceAfter=2,
            )

            story_elements.append(Paragraph("Panel Breakdown", ParagraphStyle(
                "SectionHead",
                parent=styles["Heading2"],
                fontSize=13,
                textColor=colors.HexColor("#4f46e5"),
                spaceBefore=8,
                spaceAfter=6,
            )))

            for p in script.panels:
                story_elements.append(
                    Paragraph(f"Panel {p.panel_number} — {p.mood.capitalize()}", label_style)
                )
                story_elements.append(Paragraph(p.description[:300], panel_style))
                if p.dialogue and config.include_dialogue:
                    dlg = f'<b>{p.speaker}:</b> "{p.dialogue}"' if p.speaker else f'"{p.dialogue}"'
                    story_elements.append(Paragraph(dlg, panel_style))
                story_elements.append(Spacer(1, 0.2 * cm))

        # ── Footer ────────────────────────────────────────────────────────────
        story_elements.append(HRFlowable(
            width="100%", thickness=1, color=colors.HexColor("#e5e7eb"), spaceBefore=8
        ))
        story_elements.append(Paragraph(
            "Generated by ComicCraftAI · Powered by Google Gemini",
            ParagraphStyle("Footer", parent=styles["Normal"],
                           fontSize=8, textColor=colors.HexColor("#9ca3af"),
                           alignment=TA_CENTER)
        ))

        doc.build(story_elements)
        logger.info("PDF exported → %s", output_path)
        return output_path

    def export_png(
        self,
        comic: ComicPage,
        output_path: str,
        config: Optional[ExportConfig] = None,
    ) -> str:
        """Export the assembled comic as a single high-quality PNG."""
        config = config or ExportConfig()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        if comic.assembled_image_path and Path(comic.assembled_image_path).exists():
            img = Image.open(comic.assembled_image_path).convert("RGB")
            img.save(output_path, "PNG", optimize=True)
            logger.info("PNG exported → %s", output_path)
        else:
            raise FileNotFoundError(
                f"No assembled image found for comic {comic.id}. Run layout build first."
            )

        return output_path

    def export_png_zip(
        self,
        comic: ComicPage,
        output_path: str,
        config: Optional[ExportConfig] = None,
    ) -> str:
        """Export all individual panel images as a ZIP archive."""
        config = config or ExportConfig()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        script = comic.script
        panels = script.panels if script else []

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # Include assembled page
            if comic.assembled_image_path and Path(comic.assembled_image_path).exists():
                zf.write(comic.assembled_image_path, "assembled.png")

            # Include individual panels
            for panel in panels:
                if panel.image_path and Path(panel.image_path).exists():
                    fname = f"panel_{panel.panel_number:02d}.png"
                    zf.write(panel.image_path, fname)

        with open(output_path, "wb") as f:
            f.write(buf.getvalue())

        logger.info("ZIP exported → %s", output_path)
        return output_path
