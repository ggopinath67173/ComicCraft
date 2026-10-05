import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from flask_session import Session

load_dotenv()


def create_app() -> Flask:
    """Application factory."""
    base_dir = Path(__file__).parent.parent

    app = Flask(
        __name__,
        template_folder=str(base_dir / "templates"),
        static_folder=str(base_dir / "static"),
    )

    # ── Config ────────────────────────────────────────────────────────────────
    app.config["SECRET_KEY"]       = os.getenv("FLASK_SECRET_KEY", "dev-comiccraft-secret-7x!")
    app.config["GOOGLE_API_KEY"]   = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY", "")
    app.config["SESSION_TYPE"]     = "filesystem"
    app.config["SESSION_FILE_DIR"] = str(base_dir / "flask_sessions")
    app.config["SESSION_PERMANENT"] = False

    # ── Ensure runtime directories exist ──────────────────────────────────────
    for d in [
        base_dir / "flask_sessions",
        base_dir / "static" / "generated",
        base_dir / "static" / "exports",
    ]:
        d.mkdir(parents=True, exist_ok=True)

    # ── Extensions ────────────────────────────────────────────────────────────
    Session(app)

    # ── Blueprints ────────────────────────────────────────────────────────────
    from app.routes import main_bp
    app.register_blueprint(main_bp)

    return app
