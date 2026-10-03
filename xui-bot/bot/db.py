import sqlite3
import time
from pathlib import Path

# user status flow: awaiting_name -> awaiting_phone -> pending -> approved | rejected
#                   approved <-> disabled
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    tg_id       INTEGER PRIMARY KEY,
    username    TEXT,
    name        TEXT,
    phone       TEXT,
    status      TEXT NOT NULL,
    email       TEXT UNIQUE,
    uuid        TEXT,
    sub_id      TEXT,
    created_at  INTEGER NOT NULL,
    approved_at INTEGER
);
"""


class DB:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def get(self, tg_id: int):
        return self.conn.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,)).fetchone()

    def start_registration(self, tg_id: int, username: str | None) -> None:
        self.conn.execute(
            """INSERT INTO users (tg_id, username, status, created_at) VALUES (?, ?, 'awaiting_name', ?)
               ON CONFLICT(tg_id) DO UPDATE SET username = excluded.username, status = 'awaiting_name',
                   name = NULL, phone = NULL, email = NULL, uuid = NULL, sub_id = NULL,
                   created_at = excluded.created_at, approved_at = NULL""",
            (tg_id, username, int(time.time())),
        )
        self.conn.commit()

    def update(self, tg_id: int, **fields) -> None:
        cols = ", ".join(f"{k} = ?" for k in fields)
        self.conn.execute(f"UPDATE users SET {cols} WHERE tg_id = ?", (*fields.values(), tg_id))
        self.conn.commit()

    def delete(self, tg_id: int) -> None:
        self.conn.execute("DELETE FROM users WHERE tg_id = ?", (tg_id,))
        self.conn.commit()

    def by_status(self, *statuses: str) -> list:
        marks = ",".join("?" * len(statuses))
        return self.conn.execute(
            f"SELECT * FROM users WHERE status IN ({marks}) ORDER BY created_at", statuses
        ).fetchall()

    def email_taken(self, email: str, except_tg_id: int) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM users WHERE email = ? AND tg_id != ?", (email, except_tg_id)
        ).fetchone()
        return row is not None

    def counts(self) -> dict:
        rows = self.conn.execute("SELECT status, COUNT(*) AS n FROM users GROUP BY status").fetchall()
        return {r["status"]: r["n"] for r in rows}
