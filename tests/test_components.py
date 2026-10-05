import os
import tempfile
import unittest
from pathlib import Path

from app.exporters import ComicExporter
from app.image_generator import PanelImageGenerator
from app.layout_builder import ComicLayoutBuilder
from app.models import ComicPage, ComicScript, ExportConfig, Panel


class TestLayoutAndExporter(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.out_dir = self.temp_dir.name

        self.panels = [
            Panel(
                panel_number=1,
                description="Opening scene in a cyberpunk alleyway.",
                speaker="Hero",
                dialogue="We made it.",
                caption="Night falls on Neo-Tokyo.",
                mood="mysterious",
            ),
            Panel(
                panel_number=2,
                description="A drone swoops down from above.",
                speaker="Drone",
                dialogue="Target identified!",
                caption="Incoming threat.",
                mood="tense",
            ),
            Panel(
                panel_number=3,
                description="Hero unleashes an electric strike.",
                speaker="Hero",
                dialogue="Take this!",
                caption="Sparks fly across the pavement.",
                mood="excited",
            ),
            Panel(
                panel_number=4,
                description="Hero escapes into the shadows.",
                speaker="",
                dialogue="",
                caption="Until next time...",
                mood="peaceful",
            ),
        ]

        self.script = ComicScript(
            title="Neon Shadows",
            logline="A rogue hacker dodges surveillance in the neon sprawl.",
            genre="cyberpunk",
            art_style="manga",
            color_palette="neon cyan, electric purple",
            panels=self.panels,
        )

        self.comic = ComicPage(
            script=self.script,
            layout_template="classic",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_image_generator_fallback(self):
        img_gen = PanelImageGenerator(api_key="test-key")
        panel = self.panels[0]
        img_path = img_gen.generate_panel_image(
            panel=panel,
            art_style="manga",
            color_palette="neon cyan",
            output_dir=self.out_dir,
            filename="panel_test.png",
        )
        self.assertTrue(Path(img_path).exists())
        self.assertTrue(Path(img_path).stat().st_size > 0)

    def test_layout_builder_classic(self):
        builder = ComicLayoutBuilder()
        assembled_path = builder.build(self.comic, self.out_dir)
        self.assertTrue(Path(assembled_path).exists())
        self.comic.assembled_image_path = assembled_path
        self.assertTrue(Path(assembled_path).stat().st_size > 0)

    def test_layout_builder_strip_and_feature(self):
        builder = ComicLayoutBuilder()

        self.comic.layout_template = "strip"
        strip_path = builder.build(self.comic, os.path.join(self.out_dir, "strip"))
        self.assertTrue(Path(strip_path).exists())

        self.comic.layout_template = "feature"
        feature_path = builder.build(self.comic, os.path.join(self.out_dir, "feature"))
        self.assertTrue(Path(feature_path).exists())

    def test_exporter_pdf_and_png(self):
        builder = ComicLayoutBuilder()
        assembled_path = builder.build(self.comic, self.out_dir)
        self.comic.assembled_image_path = assembled_path

        exporter = ComicExporter()
        pdf_path = os.path.join(self.out_dir, "comic.pdf")
        png_path = os.path.join(self.out_dir, "comic.png")
        zip_path = os.path.join(self.out_dir, "comic.zip")

        exporter.export_pdf(self.comic, pdf_path, ExportConfig(format="pdf"))
        self.assertTrue(Path(pdf_path).exists())
        self.assertTrue(Path(pdf_path).stat().st_size > 0)

        exporter.export_png(self.comic, png_path, ExportConfig(format="png"))
        self.assertTrue(Path(png_path).exists())
        self.assertTrue(Path(png_path).stat().st_size > 0)

        exporter.export_png_zip(self.comic, zip_path, ExportConfig(format="zip"))
        self.assertTrue(Path(zip_path).exists())
        self.assertTrue(Path(zip_path).stat().st_size > 0)


if __name__ == "__main__":
    unittest.main()
