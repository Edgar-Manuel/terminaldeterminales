from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()


@dataclass
class PanelConfig:
    id: str
    title: str
    model: str
    role: str
    system_prompt: str


@dataclass
class AppConfig:
    panels: list[PanelConfig]
    kanban_columns: list[str] = field(default_factory=lambda: ["Backlog", "In Progress", "Review", "Done"])
    workspace: Path = field(default_factory=lambda: Path(os.getenv("BRIDGE_WORKSPACE", "./workspace")).resolve())
    db_path: Path = field(default_factory=lambda: Path("./bridge.db").resolve())

    @classmethod
    def load(cls, path: str | Path = "config.json") -> "AppConfig":
        data: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
        panels = [PanelConfig(**p) for p in data["panels"]]
        cols = data.get("kanban", {}).get("columns", ["Backlog", "In Progress", "Review", "Done"])
        cfg = cls(panels=panels, kanban_columns=cols)
        cfg.workspace.mkdir(parents=True, exist_ok=True)
        return cfg
