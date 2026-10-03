import sqlite3
import time
from pathlib import Path

# user status flow: awaiting_name -> awaiting_phone -> pending -> approved | rejected
#                   approved <-> disabled
# low_alerted: 1 once the low-traffic warning was sent; cleared when the quota is back above the threshold.
# extra_requested_at: set while a "more traffic" request waits for the admin.
# web_token: secret for the status page of a request sent from the web form. Web users are stored
#   under a negative placeholder tg_id until they start the bot and share the same phone number (link()).
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

# Columns added after the first release; added to existing databases on startup.
MIGRATIONS = {
    "low_alerted": "INTEGER NOT NULL DEFAULT 0",
    "extra_requested_at": "INTEGER",
    "web_token": "TEXT",
}


class DB:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        have = {r["name"] for r in self.conn.execute("PRAGMA table_info(users)")}
        for col, decl in MIGRATIONS.items():
            if col not in have:
                self.conn.execute(f"ALTER TABLE users ADD COLUMN {col} {decl}")
        self.conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_web_token ON users (web_token)")
        self.conn.commit()

    def get(self, tg_id: int):
        return self.conn.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,)).fetchone()

    def start_registration(self, tg_id: int, username: str | None) -> None:
        self.conn.execute(
            """INSERT INTO users (tg_id, username, status, created_at) VALUES (?, ?, 'awaiting_name', ?)
               ON CONFLICT(tg_id) DO UPDATE SET username = excluded.username, status = 'awaiting_name',
                   name = NULL, phone = NULL, email = NULL, uuid = NULL, sub_id = NULL,
                   created_at = excluded.created_at, approved_at = NULL,
                   low_alerted = 0, extra_requested_at = NULL""",
            (tg_id, username, int(time.time())),
        )
        self.conn.commit()

    # ---- web requests
    def add_web_request(self, name: str, phone: str, token: str, status: str = "pending") -> int:
        """Store a user without Telegram (web form, or added by the admin) under a fresh negative
        placeholder ID and return that ID."""
        with self.conn:
            # A rejected earlier web request with this number makes way for the new one.
            self.conn.execute("DELETE FROM users WHERE phone = ? AND tg_id < 0 AND status = 'rejected'", (phone,))
            placeholder = min(self.conn.execute("SELECT MIN(tg_id) FROM users").fetchone()[0] or 0, 0) - 1
            self.conn.execute(
                """INSERT INTO users (tg_id, name, phone, status, web_token, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (placeholder, name, phone, status, token, int(time.time())),
            )
        return placeholder

    def by_token(self, token: str):
        return self.conn.execute("SELECT * FROM users WHERE web_token = ?", (token,)).fetchone()

    def active_by_phone(self, phone: str):
        """The account (or waiting request) that already uses this number, if any."""
        return self.conn.execute(
            "SELECT * FROM users WHERE phone = ? AND status IN ('pending', 'approved', 'disabled')", (phone,)
        ).fetchone()

    def phone_in_use(self, phone: str) -> bool:
        return self.active_by_phone(phone) is not None

    def web_by_phone(self, phone: str):
        """A web request with this number that is not yet tied to a Telegram account."""
        return self.conn.execute(
            "SELECT * FROM users WHERE phone = ? AND tg_id < 0 AND status IN ('pending', 'approved', 'disabled')",
            (phone,),
        ).fetchone()

    def link(self, placeholder: int, tg_id: int, username: str | None) -> None:
        """Move a web user onto their Telegram ID, replacing the registration they just went through."""
        with self.conn:
            self.conn.execute("DELETE FROM users WHERE tg_id = ?", (tg_id,))
            self.conn.execute("UPDATE users SET tg_id = ?, username = ? WHERE tg_id = ?", (tg_id, username, placeholder))

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

    def extra_requests(self) -> list:
        return self.conn.execute(
            "SELECT * FROM users WHERE extra_requested_at IS NOT NULL ORDER BY extra_requested_at"
        ).fetchall()

    def email_taken(self, email: str, except_tg_id: int) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM users WHERE email = ? AND tg_id != ?", (email, except_tg_id)
        ).fetchone()
        return row is not None

    def counts(self) -> dict:
        rows = self.conn.execute("SELECT status, COUNT(*) AS n FROM users GROUP BY status").fetchall()
        return {r["status"]: r["n"] for r in rows}
