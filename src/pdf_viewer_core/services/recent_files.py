# src/pdf_viewer_core/services/recent_files.py
from __future__ import annotations

import json
from pathlib import Path


class RecentFiles:
    def __init__(self, app_name: str, limit: int = 10) -> None:
        self._limit = limit
        self._path = self._default_store_path(app_name)

    def _default_store_path(self, app_name: str) -> Path:
        base = Path.home() / ".pdf_viewer_core"
        base.mkdir(parents=True, exist_ok=True)
        return base / f"{app_name}_recent.json"

    def _load(self) -> list[str]:
        if not self._path.exists():
            return []
        try:
            return list(json.loads(self._path.read_text(encoding="utf-8")))
        except Exception:
            return []

    def _save(self, items: list[str]) -> None:
        self._path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_paths(self) -> list[str]:
        return self._load()

    def get_last(self) -> str | None:
        items = self._load()
        return items[0] if items else None

    def push(self, path: str) -> None:
        items = [p for p in self._load() if p != path]
        items.insert(0, path)
        items = items[: self._limit]
        self._save(items)
