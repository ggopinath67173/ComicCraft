"""
Unit tests for ComicCraftAI.

Run with:
    python -m pytest tests/ -v
"""

import json
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure the app root is on the path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from app.models import ComicPage, ComicScript, ExportConfig, Panel


# ─────────────────────────────────────────────────────────────────────────────
# Model Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPanel(unittest.TestCase):

    def test_panel_defaults(self):
        panel = Panel()
        self.assertIsNotNone(panel.id)
        self.assertEqual(panel.panel_number, 0)
        self.assertEqual(panel.mood, "neutral")

    def test_panel_serialization(self):
        panel = Panel(panel_number=1, description="A wide shot.", dialogue="Hello!", speaker="Hero")
        d = panel.to_dict()
        self.assertEqual(d["panel_number"], 1)
        self.assertEqual(d["dialogue"], "Hello!")
        restored = Panel.from_dict(d)
        self.assertEqual(restored.panel_number, 1)
        self.assertEqual(restored.speaker, "Hero")

    def test_panel_from_dict_ignores_unknown_keys(self):
        d = {"panel_number": 2, "description": "test", "unknown_key": "should be ignored"}
        panel = Panel.from_dict(d)
        self.assertEqual(panel.panel_number, 2)
        self.assertFalse(hasattr(panel, "unknown_key"))


class TestComicScript(unittest.TestCase):

    def _make_script(self) -> ComicScript:
        return ComicScript(
            title="Test Comic",
            logline="A test story.",
            genre="adventure",
            art_style="manga",
            panels=[
                Panel(panel_number=1, description="Opening scene."),
                Panel(panel_number=2, description="Rising action."),
            ],
        )

    def test_script_roundtrip(self):
        script = self._make_script()
        d = script.to_dict()
        restored = ComicScript.from_dict(d)
        self.assertEqual(restored.title, "Test Comic")
        self.assertEqual(len(restored.panels), 2)
        self.assertEqual(restored.panels[0].description, "Opening scene.")

    def test_panels_preserved(self):
        script = self._make_script()
        d = script.to_dict()
        restored = ComicScript.from_dict(d)
        self.assertEqual(restored.panels[1].panel_number, 2)


class TestComicPage(unittest.TestCase):

    def test_page_roundtrip(self):
        script = ComicScript(title="Page Test", panels=[Panel(panel_number=1)])
        page = ComicPage(script=script, layout_template="classic")
        d = page.to_dict()
        restored = ComicPage.from_dict(d)
        self.assertEqual(restored.layout_template, "classic")
        self.assertIsNotNone(restored.script)
        self.assertEqual(restored.script.title, "Page Test")

    def test_page_without_script(self):
        page = ComicPage()
        d = page.to_dict()
        self.assertIsNone(d["script"])
        restored = ComicPage.from_dict(d)
        self.assertIsNone(restored.script)


# ─────────────────────────────────────────────────────────────────────────────
# Flask Route Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestFlaskRoutes(unittest.TestCase):

    def setUp(self):
        os.environ.setdefault("FLASK_SECRET_KEY", "test-secret")
        # Don't require a real API key for route tests
        os.environ.setdefault("GOOGLE_API_KEY", "test-key-placeholder")

        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

    def test_index_returns_200(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"ComicCraftAI", res.data)

    def test_generate_missing_prompt_returns_400(self):
        res = self.client.post(
            "/generate",
            data=json.dumps({"prompt": ""}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        body = json.loads(res.data)
        self.assertFalse(body["success"])

    def test_generate_no_json_body_returns_400(self):
        res = self.client.post("/generate", content_type="application/json", data="{}")
        self.assertEqual(res.status_code, 400)

    def test_preview_nonexistent_comic_redirects(self):
        res = self.client.get("/preview/nonexistent-id-12345")
        self.assertEqual(res.status_code, 302)   # redirect to /

    def test_health_endpoint(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        body = json.loads(res.data)
        self.assertEqual(body["status"], "ok")

    def test_export_nonexistent_comic(self):
        res = self.client.post(
            "/export",
            data=json.dumps({"comic_id": "fake-id", "format": "pdf"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 404)

    def test_export_invalid_format(self):
        res = self.client.post(
            "/export",
            data=json.dumps({"comic_id": "any", "format": "mp3"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)


# ─────────────────────────────────────────────────────────────────────────────
# StoryGenerator Tests (mocked)
# ─────────────────────────────────────────────────────────────────────────────

class TestStoryGeneratorFallback(unittest.TestCase):
    """Test that the fallback script is sane when the API is unavailable."""

    def setUp(self):
        os.environ["GOOGLE_API_KEY"] = "test-dummy-key"

    def test_fallback_script_has_correct_panel_count(self):
        from app.gemini_flash import StoryGenerator
        gen = StoryGenerator(api_key="test-key")
        script = gen._fallback_script("A robot learns to dance.", "comedy", "cartoon", 6)
        self.assertEqual(len(script.panels), 6)
        self.assertEqual(script.genre, "comedy")
        self.assertEqual(script.art_style, "cartoon")

    def test_fallback_script_fields(self):
        from app.gemini_flash import StoryGenerator
        gen = StoryGenerator(api_key="test-key")
        script = gen._fallback_script("A story.", "adventure", "manga", 4)
        self.assertIsNotNone(script.title)
        for i, p in enumerate(script.panels):
            self.assertEqual(p.panel_number, i + 1)
            self.assertIsNotNone(p.id)

    @patch("app.gemini_flash.genai")
    def test_parse_response_valid_json(self, mock_genai):
        """_parse_response correctly parses well-formed JSON."""
        from app.gemini_flash import StoryGenerator
        gen = StoryGenerator(api_key="test-key")

        raw = json.dumps({
            "title": "Test Title",
            "logline": "A brief logline.",
            "color_palette": "red, blue, gold",
            "panels": [
                {
                    "panel_number": 1,
                    "description": "A wide establishing shot.",
                    "speaker": "Hero",
                    "dialogue": "Ready for adventure!",
                    "caption": "",
                    "mood": "excited",
                    "characters": ["Hero"],
                }
            ],
        })

        script = gen._parse_response(raw, "adventure", "manga")
        self.assertEqual(script.title, "Test Title")
        self.assertEqual(len(script.panels), 1)
        self.assertEqual(script.panels[0].mood, "excited")
        self.assertEqual(script.panels[0].speaker, "Hero")


# ─────────────────────────────────────────────────────────────────────────────
# ExportConfig Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestExportConfig(unittest.TestCase):

    def test_defaults(self):
        cfg = ExportConfig()
        self.assertEqual(cfg.format, "pdf")
        self.assertTrue(cfg.include_captions)
        self.assertTrue(cfg.include_dialogue)

    def test_custom(self):
        cfg = ExportConfig(format="png", include_captions=False)
        self.assertEqual(cfg.format, "png")
        self.assertFalse(cfg.include_captions)


if __name__ == "__main__":
    unittest.main()
