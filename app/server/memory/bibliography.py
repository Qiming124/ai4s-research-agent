# 参考文献库：BibTeX 存储与去重。

from __future__ import annotations

import json
import re
import sqlite3
import threading
from typing import Any

from server.config import get_settings

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS bibliography (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  TEXT NOT NULL DEFAULT 'default',
    bib_key     TEXT NOT NULL,
    title       TEXT NOT NULL DEFAULT '',
    authors     TEXT NOT NULL DEFAULT '',
    year        TEXT NOT NULL DEFAULT '',
    arxiv_id    TEXT NOT NULL DEFAULT '',
    doi         TEXT NOT NULL DEFAULT '',
    raw_bibtex  TEXT NOT NULL DEFAULT '',
    metadata    TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(project_id, bib_key)
);

CREATE INDEX IF NOT EXISTS idx_bib_project ON bibliography(project_id);
CREATE INDEX IF NOT EXISTS idx_bib_arxiv ON bibliography(arxiv_id);
"""


class BibliographyStore:
    def __init__(self, db_path: str) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA_SQL)
            self._conn.commit()

    def upsert(
        self,
        *,
        project_id: str = "default",
        bib_key: str,
        title: str = "",
        authors: str = "",
        year: str = "",
        arxiv_id: str = "",
        doi: str = "",
        raw_bibtex: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO bibliography
                (project_id, bib_key, title, authors, year, arxiv_id, doi, raw_bibtex, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, bib_key) DO UPDATE SET
                    title=excluded.title, authors=excluded.authors, year=excluded.year,
                    arxiv_id=excluded.arxiv_id, doi=excluded.doi,
                    raw_bibtex=excluded.raw_bibtex, metadata=excluded.metadata
                """,
                (
                    project_id,
                    bib_key,
                    title,
                    authors,
                    year,
                    arxiv_id,
                    doi,
                    raw_bibtex,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
            row = self._conn.execute(
                "SELECT * FROM bibliography WHERE project_id = ? AND bib_key = ?",
                (project_id, bib_key),
            ).fetchone()
            self._conn.commit()
        return self._row(row)

    def find_by_arxiv(self, arxiv_id: str, project_id: str = "default") -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM bibliography WHERE project_id = ? AND arxiv_id = ?",
                (project_id, arxiv_id),
            ).fetchone()
        return self._row(row) if row else None

    def list_entries(self, project_id: str = "default", limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM bibliography WHERE project_id = ? ORDER BY id DESC LIMIT ?",
                (project_id, limit),
            ).fetchall()
        return [self._row(r) for r in rows]

    def export_bibtex(self, project_id: str = "default") -> str:
        entries = self.list_entries(project_id=project_id, limit=500)
        parts: list[str] = []
        for e in entries:
            if e.get("raw_bibtex"):
                parts.append(e["raw_bibtex"])
            else:
                parts.append(
                    f"@article{{{e['bib_key']},\n"
                    f"  title = {{{e['title']}}},\n"
                    f"  author = {{{e['authors']}}},\n"
                    f"  year = {{{e['year']}}},\n"
                    f"  eprint = {{{e['arxiv_id']}}},\n"
                    f"}}"
                )
        return "\n\n".join(parts)

    @staticmethod
    def bib_key_from_arxiv(arxiv_id: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9]", "", arxiv_id)
        return f"arxiv{clean[:16]}"

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            return {}
        return {
            "id": row["id"],
            "project_id": row["project_id"],
            "bib_key": row["bib_key"],
            "title": row["title"],
            "authors": row["authors"],
            "year": row["year"],
            "arxiv_id": row["arxiv_id"],
            "doi": row["doi"],
            "raw_bibtex": row["raw_bibtex"],
            "metadata": json.loads(row["metadata"] or "{}"),
            "created_at": row["created_at"],
        }


_bib_store: BibliographyStore | None = None


def get_bibliography_store() -> BibliographyStore:
    global _bib_store
    if _bib_store is None:
        settings = get_settings()
        _bib_store = BibliographyStore(settings.session_db_path)
    return _bib_store
