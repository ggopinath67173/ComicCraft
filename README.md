# ComicCraftAI 🎨⚡

> Create stunning multi-panel comic strips powered by Google Gemini and Imagen 3.

ComicCraftAI transforms your story ideas into full comic book strips with coherent scripts, panel descriptions, dynamic illustrations, and multi-format exports (PDF, PNG, ZIP).

---

## ✨ Features

- **Story & Script Generation**: Powered by **Gemini 2.5 Flash** for blazing fast scripting, or **Gemini 2.5 Pro** for enhanced narrative depth.
- **AI Panel Illustrations**: Integrated with **Google Imagen 3** with consistent mood-driven palettes and styles (Manga, Superhero, Noir, Watercolor, Cartoon, Anime, etc.).
- **Rich Fallback Mode**: Generates beautiful graphic panel placeholders with captions even without API quota or offline.
- **Multiple Layout Templates**:
  - `Classic`: 2-column comic page grid
  - `Strip`: Newspaper-style horizontal or vertical comic strip
  - `Story`: Multi-panel graphic novel layout
  - `Feature`: Dynamic hero panel with supporting beats
- **Interactive Preview & Regeneration**: Edit captions and re-generate individual panels on the fly.
- **Multi-Format Exporter**:
  - **PDF**: High-resolution print-ready document formatted with ReportLab.
  - **PNG**: Single assembled high-res composite image.
  - **ZIP**: High-resolution bundle containing individual panel art and the full strip.
- **Dark Glassmorphic UI**: Premium responsive interface built with vanilla modern CSS and interactive UI animations.

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.11 or newer
- (Optional) A Google AI Studio API Key ([Get one here](https://aistudio.google.com/))

### 2. Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/your-username/ComicCraftAI.git
cd ComicCraftAI
pip install -r requirements.txt
```

### 3. Configure Environment

Copy `.env.example` to `.env`:

```bash
copy .env.example .env
```

Open `.env` and insert your Google API key:

```env
GOOGLE_API_KEY=your_google_api_key_here
FLASK_SECRET_KEY=super-secret-key-change-in-production
GEMINI_FLASH_MODEL=gemini-2.5-flash
GEMINI_PRO_MODEL=gemini-2.5-pro
IMAGEN_MODEL=imagen-3.0-generate-002
```

*(Note: Even without a Google API key, ComicCraftAI will run in fallback demonstration mode with full layout generation and exports!)*

### 4. Run the Application

Start the Flask development server:

```bash
python run.py
```

Then visit [http://localhost:5000](http://localhost:5000) in your browser.

---

## 🧪 Testing

Run the automated test suite with `pytest`:

```bash
python -m pytest tests/ -v
```

All 23 unit and integration tests cover data serialization, Gemini script parsing, fallback handling, Flask HTTP endpoints, layout composition, and PDF/PNG exporters.

---

## 📂 Project Architecture

```
ComicCraftAI/
├── app/
│   ├── __init__.py           # Flask app factory, session & directory initialization
│   ├── models.py             # Data models: Panel, ComicScript, ComicPage, ExportConfig
│   ├── routes.py             # HTTP routes: generate, preview, regenerate, export, health
│   ├── gemini_flash.py       # StoryGenerator (Gemini 2.5 Flash + fallback)
│   ├── gemini_pro.py         # QualityGenerator (Gemini 2.5 Pro)
│   ├── image_generator.py    # PanelImageGenerator (Imagen 3 + PIL stylized generator)
│   ├── layout_builder.py     # ComicLayoutBuilder (Classic, Strip, Feature, Story)
│   └── exporters.py          # ComicExporter (ReportLab PDF, PNG, ZIP)
├── static/
│   ├── css/
│   │   └── style.css         # Dark glassmorphic design system
│   ├── generated/            # Comic output working directories
│   └── exports/              # Final exported files
├── templates/
│   ├── index.html            # Generator landing page & settings form
│   ├── comic_preview.html    # Interactive comic preview & panel regeneration
│   └── export_success.html   # Download & celebration screen
├── tests/
│   ├── test_app.py           # Unit tests for models, routes, scripts
│   └── test_components.py    # Integration tests for layout, PIL, and exporters
├── requirements.txt          # Python dependencies
├── run.py                    # Local development server entrypoint
└── .env.example              # Environment variables template
```

---

## 📄 License

MIT License. Feel free to use, modify, and build upon ComicCraftAI!
