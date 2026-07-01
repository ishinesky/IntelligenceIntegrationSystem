from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Optional

from .models import ColumnConfig, utc_now_iso


class ColumnStore:
    """File-backed storage for MVP column definitions.

    The production version can replace this with MongoDB. Keeping MVP data in JSON
    makes it reviewable, diffable, and safe for AI-assisted column creation.
    """

    def __init__(self, root: str | Path = "ColumnMVP/columns"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, column_id: str) -> Path:
        return self.root / f"{column_id}.json"

    def save(self, column: ColumnConfig, overwrite: bool = False) -> Path:
        path = self.path_for(column.id)
        if path.exists() and not overwrite:
            raise FileExistsError(f"Column already exists: {path}")
        column.updated_at = utc_now_iso()
        with path.open("w", encoding="utf-8") as f:
            json.dump(column.to_dict(), f, ensure_ascii=False, indent=2)
        return path

    def load(self, column_id: str) -> ColumnConfig:
        path = self.path_for(column_id)
        with path.open("r", encoding="utf-8") as f:
            return ColumnConfig.from_dict(json.load(f))

    def list_paths(self) -> List[Path]:
        return sorted(self.root.glob("*.json"))

    def list_columns(self, enabled_only: bool = True) -> List[ColumnConfig]:
        columns: List[ColumnConfig] = []
        for path in self.list_paths():
            try:
                with path.open("r", encoding="utf-8") as f:
                    column = ColumnConfig.from_dict(json.load(f))
            except Exception as exc:
                print(f"[ColumnStore] skip invalid column file {path}: {exc}")
                continue
            if enabled_only and not column.enabled:
                continue
            columns.append(column)
        return columns

    def extend_sources(self, column_id: str, sources: Iterable, overwrite: bool = True) -> Path:
        column = self.load(column_id)
        existing_urls = {source.url for source in column.sources}
        for source in sources:
            if source.url not in existing_urls:
                column.sources.append(source)
                existing_urls.add(source.url)
        return self.save(column, overwrite=overwrite)

    def find_by_name(self, name: str) -> Optional[ColumnConfig]:
        for column in self.list_columns(enabled_only=False):
            if column.name == name:
                return column
        return None
