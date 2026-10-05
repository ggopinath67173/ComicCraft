from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class Panel:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    panel_number: int = 0
    description: str = ""
    speaker: str = ""
    dialogue: str = ""
    caption: str = ""
    mood: str = "neutral"
    characters: list[str] = field(default_factory=list)
    image_path: Optional[str] = None
    image_url: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "panel_number": self.panel_number,
            "description": self.description,
            "speaker": self.speaker,
            "dialogue": self.dialogue,
            "caption": self.caption,
            "mood": self.mood,
            "characters": list(self.characters),
            "image_path": self.image_path,
            "image_url": self.image_url,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Panel:
        valid_fields = {
            "id",
            "panel_number",
            "description",
            "speaker",
            "dialogue",
            "caption",
            "mood",
            "characters",
            "image_path",
            "image_url",
        }
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


@dataclass
class ComicScript:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "Untitled Comic"
    logline: str = ""
    genre: str = "adventure"
    art_style: str = "manga"
    color_palette: str = ""
    panels: list[Panel] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "logline": self.logline,
            "genre": self.genre,
            "art_style": self.art_style,
            "color_palette": self.color_palette,
            "panels": [p.to_dict() for p in self.panels],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ComicScript:
        panels_data = data.get("panels", [])
        panels = [Panel.from_dict(p) if isinstance(p, dict) else p for p in panels_data]
        valid_fields = {
            "id",
            "title",
            "logline",
            "genre",
            "art_style",
            "color_palette",
        }
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(panels=panels, **filtered)


@dataclass
class ComicPage:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    script: Optional[ComicScript] = None
    layout_template: str = "classic"
    assembled_image_path: Optional[str] = None
    assembled_image_url: Optional[str] = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "script": self.script.to_dict() if self.script else None,
            "layout_template": self.layout_template,
            "assembled_image_path": self.assembled_image_path,
            "assembled_image_url": self.assembled_image_url,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ComicPage:
        script_data = data.get("script")
        script = ComicScript.from_dict(script_data) if script_data else None
        valid_fields = {
            "id",
            "layout_template",
            "assembled_image_path",
            "assembled_image_url",
            "created_at",
        }
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(script=script, **filtered)


@dataclass
class ExportConfig:
    format: str = "pdf"
    include_captions: bool = True
    include_dialogue: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExportConfig:
        valid_fields = {"format", "include_captions", "include_dialogue"}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)