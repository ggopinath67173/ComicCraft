import json
import logging
import os
from pathlib import Path

from flask import (
    Blueprint, current_app, jsonify, redirect,
    render_template, request, send_from_directory, url_for,
)

from app.exporters import ComicExporter
from app.image_generator import PanelImageGenerator
from app.layout_builder import ComicLayoutBuilder
from app.models import ComicPage, ExportConfig

logger = logging.getLogger(__name__)

main_bp = Blueprint("main", __name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _generated_dir(comic_id: str) -> Path:
    """Return the directory that holds all files for a given comic."""
    return Path(current_app.static_folder) / "generated" / comic_id


def _load_comic(comic_id: str) -> ComicPage | None:
    """Load a ComicPage from its persisted JSON file, or return None."""
    data_path = _generated_dir(comic_id) / "data.json"
    if not data_path.exists():
        return None
    try:
        with open(data_path, encoding="utf-8") as f:
            return ComicPage.from_dict(json.load(f))
    except Exception as exc:
        logger.error("Failed to load comic %s: %s", comic_id, exc)
        return None


def _save_comic(comic: ComicPage):
    """Persist a ComicPage as JSON."""
    out = _generated_dir(comic.id) / "data.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(comic.to_dict(), f, indent=2)


def _api_key() -> str:
    return current_app.config.get("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route("/")
def index():
    """Landing page — prompt form."""
    return render_template("index.html")


@main_bp.route("/generate", methods=["POST"])
def generate():
    """
    Generate a full comic from the submitted form data.

    Accepts JSON body:
        prompt       : str  (required)
        genre        : str  (default: adventure)
        art_style    : str  (default: manga)
        panel_count  : int  (default: 4)
        layout       : str  (default: classic)
        quality      : str  flash | pro  (default: flash)
        characters   : str  (optional)

    Returns JSON:
        { success, comic_id, redirect }   on success
        { success: false, error }         on failure
    """
    data = request.get_json(silent=True) or {}

    prompt      = data.get("prompt", "").strip()
    genre       = data.get("genre", "adventure")
    art_style   = data.get("art_style", "manga")
    panel_count = min(max(int(data.get("panel_count", 4)), 3), 8)
    layout      = data.get("layout", "classic")
    quality     = data.get("quality", "flash")
    characters  = data.get("characters", "")

    if not prompt:
        return jsonify({"success": False, "error": "Story prompt is required."}), 400

    if not _api_key():
        return jsonify({
            "success": False,
            "error": "GOOGLE_API_KEY not configured. Please set it in your .env file."
        }), 500

    try:
        # ── 1. Generate script ────────────────────────────────────────────────
        if quality == "pro":
            from app.gemini_pro import QualityGenerator
            generator = QualityGenerator(api_key=_api_key())
        else:
            from app.gemini_flash import StoryGenerator
            generator = StoryGenerator(api_key=_api_key())

        logger.info("Generating script (quality=%s, panels=%d) ...", quality, panel_count)
        script = generator.generate_script(
            prompt=prompt,
            genre=genre,
            panel_count=panel_count,
            art_style=art_style,
            characters=characters,
        )

        # ── 2. Create comic object & working directory ─────────────────────────
        comic     = ComicPage(script=script, layout_template=layout)
        out_dir   = _generated_dir(comic.id)
        out_dir.mkdir(parents=True, exist_ok=True)

        # ── 3. Generate panel images ──────────────────────────────────────────
        img_gen = PanelImageGenerator(api_key=_api_key())

        for panel in script.panels:
            logger.info("Generating image for panel %d ...", panel.panel_number)
            img_path = img_gen.generate_panel_image(
                panel=panel,
                art_style=script.art_style,
                color_palette=script.color_palette,
                output_dir=str(out_dir),
            )
            panel.image_path = img_path
            panel.image_url  = f"/static/generated/{comic.id}/{Path(img_path).name}"

        # ── 4. Assemble layout ────────────────────────────────────────────────
        logger.info("Building layout (%s) ...", layout)
        builder = ComicLayoutBuilder()
        assembled = builder.build(comic, str(out_dir))
        comic.assembled_image_path = assembled
        comic.assembled_image_url  = f"/static/generated/{comic.id}/assembled.png"

        # ── 5. Persist ────────────────────────────────────────────────────────
        _save_comic(comic)
        logger.info("Comic %s created successfully.", comic.id)

        return jsonify({
            "success":  True,
            "comic_id": comic.id,
            "redirect": url_for("main.preview", comic_id=comic.id),
        })

    except Exception as exc:
        logger.exception("Generation failed: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@main_bp.route("/preview/<comic_id>")
def preview(comic_id: str):
    """Display the assembled comic with per-panel editing controls."""
    comic = _load_comic(comic_id)
    if comic is None:
        return redirect(url_for("main.index"))
    return render_template("comic_preview.html", comic=comic)


@main_bp.route("/regenerate-panel", methods=["POST"])
def regenerate_panel():
    """
    Regenerate the image for a single panel.

    Accepts JSON body: { comic_id, panel_id }
    Returns JSON:      { success, image_url, assembled_url }
    """
    data     = request.get_json(silent=True) or {}
    comic_id = data.get("comic_id", "")
    panel_id = data.get("panel_id", "")

    comic = _load_comic(comic_id)
    if comic is None:
        return jsonify({"success": False, "error": "Comic not found."}), 404

    target_panel = next(
        (p for p in comic.script.panels if p.id == panel_id), None
    )
    if target_panel is None:
        return jsonify({"success": False, "error": "Panel not found."}), 404

    try:
        out_dir = _generated_dir(comic_id)
        img_gen = PanelImageGenerator(api_key=_api_key())

        img_path = img_gen.generate_panel_image(
            panel=target_panel,
            art_style=comic.script.art_style,
            color_palette=comic.script.color_palette,
            output_dir=str(out_dir),
            filename=f"panel_{target_panel.panel_number:02d}_{target_panel.id}_r.png",
        )
        target_panel.image_path = img_path
        target_panel.image_url  = f"/static/generated/{comic_id}/{Path(img_path).name}"

        # Rebuild assembled layout
        builder  = ComicLayoutBuilder()
        assembled = builder.build(comic, str(out_dir))
        comic.assembled_image_path = assembled
        comic.assembled_image_url  = f"/static/generated/{comic_id}/assembled.png"

        _save_comic(comic)

        return jsonify({
            "success":      True,
            "image_url":    target_panel.image_url,
            "assembled_url": comic.assembled_image_url,
        })

    except Exception as exc:
        logger.exception("Panel regeneration failed: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@main_bp.route("/export", methods=["POST"])
def export_comic():
    """
    Export the comic to the requested format.

    Accepts JSON body: { comic_id, format }   format: pdf | png | zip
    Returns JSON:      { success, download_url, filename }
    """
    data     = request.get_json(silent=True) or {}
    comic_id = data.get("comic_id", "")
    fmt      = data.get("format", "pdf").lower()

    if fmt not in ("pdf", "png", "zip"):
        return jsonify({"success": False, "error": f"Unsupported format: {fmt}"}), 400

    comic = _load_comic(comic_id)
    if comic is None:
        return jsonify({"success": False, "error": "Comic not found."}), 404

    try:
        exports_dir = Path(current_app.static_folder) / "exports"
        exports_dir.mkdir(exist_ok=True)

        safe_title = "".join(
            c if c.isalnum() or c in ("-", "_") else "_"
            for c in (comic.script.title if comic.script else "comic")
        )[:40]
        filename = f"{safe_title}_{comic_id[:8]}.{fmt if fmt != 'zip' else 'zip'}"
        out_path = str(exports_dir / filename)

        exporter = ComicExporter()
        config   = ExportConfig(format=fmt)

        if fmt == "pdf":
            exporter.export_pdf(comic, out_path, config)
        elif fmt == "png":
            exporter.export_png(comic, out_path, config)
        else:
            exporter.export_png_zip(comic, out_path, config)

        return jsonify({
            "success":      True,
            "filename":     filename,
            "download_url": url_for("main.download_export", filename=filename),
            "redirect":     url_for(
                "main.export_success",
                filename=filename,
                comic_id=comic_id,
                fmt=fmt,
            ),
        })

    except Exception as exc:
        logger.exception("Export failed: %s", exc)
        return jsonify({"success": False, "error": str(exc)}), 500


@main_bp.route("/export/download/<path:filename>")
def download_export(filename: str):
    """Serve an exported file as a download attachment."""
    exports_dir = Path(current_app.static_folder) / "exports"
    return send_from_directory(str(exports_dir), filename, as_attachment=True)


@main_bp.route("/export/success")
def export_success():
    """Export confirmation page."""
    filename = request.args.get("filename", "")
    comic_id = request.args.get("comic_id", "")
    fmt      = request.args.get("fmt", "pdf")

    comic = _load_comic(comic_id) if comic_id else None
    return render_template(
        "export_success.html",
        filename=filename,
        comic_id=comic_id,
        fmt=fmt,
        comic=comic,
        download_url=url_for("main.download_export", filename=filename),
    )


@main_bp.route("/health")
def health():
    """Simple health-check endpoint."""
    return jsonify({"status": "ok", "api_key_set": bool(_api_key())})
