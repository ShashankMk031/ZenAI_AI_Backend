import sqlite3
import os
from datetime import datetime


class CacheManager:
    """
    Simple SQLite cache for last known project summaries.
    """

    def __init__(self):
        self.db_path = os.path.join(os.getcwd(), "zenai_cache.db")
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT,
                markdown TEXT,
                summary TEXT
            )
        """)
        conn.commit()
        conn.close()

    def save_report(self, markdown: str, summary: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO reports (created_at, markdown, summary) VALUES (?, ?, ?)",
            (datetime.utcnow().isoformat(), markdown, summary)
        )
        conn.commit()
        conn.close()

    def get_latest_report(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT markdown, summary, created_at FROM reports ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return {"markdown": row[0], "summary": row[1], "created_at": row[2]}
        return None
