from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

import aiosqlite


SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    panel_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author TEXT NOT NULL,
    tag TEXT,
    content TEXT NOT NULL,
    ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    column_name TEXT NOT NULL,
    assignee TEXT,
    ts REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_panel ON messages(panel_id);
CREATE INDEX IF NOT EXISTS idx_notes_tag ON notes(tag);
"""


@dataclass
class MemoryEntry:
    id: int
    panel_id: str
    role: str
    content: str
    ts: float


class SharedMemory:
    """SQLite-backed shared memory accessible by every panel/agent.

    Stores chat history per panel plus a global feed all agents can read.
    """

    def __init__(self, db_path: str | Path = "bridge.db") -> None:
        self.db_path = str(db_path)
        self.init_sync()

    def init_sync(self) -> None:
        """Create schema synchronously so widgets can read immediately."""
        with sqlite3.connect(self.db_path) as db:
            db.executescript(SCHEMA)
            db.commit()

    async def init(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(SCHEMA)
            await db.commit()

    async def add_message(self, panel_id: str, role: str, content: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO messages (panel_id, role, content, ts) VALUES (?, ?, ?, ?)",
                (panel_id, role, content, time.time()),
            )
            await db.commit()

    async def get_history(self, panel_id: str, limit: int = 50) -> list[MemoryEntry]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT id, panel_id, role, content, ts FROM messages "
                "WHERE panel_id = ? ORDER BY id DESC LIMIT ?",
                (panel_id, limit),
            )
            rows = await cursor.fetchall()
        return [MemoryEntry(*row) for row in reversed(rows)]

    async def add_note(self, author: str, content: str, tag: str | None = None) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO notes (author, tag, content, ts) VALUES (?, ?, ?, ?)",
                (author, tag, content, time.time()),
            )
            await db.commit()

    async def recent_notes(self, limit: int = 20, tag: str | None = None) -> list[dict]:
        query = "SELECT author, tag, content, ts FROM notes"
        params: tuple = ()
        if tag:
            query += " WHERE tag = ?"
            params = (tag,)
        query += " ORDER BY id DESC LIMIT ?"
        params = (*params, limit)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
        return [
            {"author": r[0], "tag": r[1], "content": r[2], "ts": r[3]}
            for r in reversed(rows)
        ]

    async def add_task(
        self,
        title: str,
        description: str = "",
        column: str = "Backlog",
        assignee: str | None = None,
    ) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO tasks (title, description, column_name, assignee, ts) "
                "VALUES (?, ?, ?, ?, ?)",
                (title, description, column, assignee, time.time()),
            )
            await db.commit()
            return cursor.lastrowid or 0

    async def move_task(self, task_id: int, column: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE tasks SET column_name = ? WHERE id = ?", (column, task_id)
            )
            await db.commit()

    async def delete_task(self, task_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            await db.commit()

    async def list_tasks(self) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT id, title, description, column_name, assignee, ts "
                "FROM tasks ORDER BY id ASC"
            )
            rows = await cursor.fetchall()
        return [
            {
                "id": r[0],
                "title": r[1],
                "description": r[2],
                "column": r[3],
                "assignee": r[4],
                "ts": r[5],
            }
            for r in rows
        ]
