"""
File Memory — Store files in JARVIS memory and use them as context.

Allows JARVIS to remember file contents so you can say:
  "Store this file in your memory" → JARVIS reads + indexes the file
  "Keep these instructions in mind" → JARVIS uses file content as context
  "What does the spec say about authentication?" → JARVIS searches stored files

Stores:
  - File path + name + content (or summary for large files)
  - Metadata: when stored, last accessed, tags
  - Full text search via SQLite FTS5

Files are stored in data/jarvis.db alongside other memories.
"""

import json
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger("jarvis.file_memory")

DB_PATH = Path(__file__).parent / "data" / "jarvis.db"
MAX_FILE_SIZE_BYTES = 500_000   # 500KB — larger files get summarized
MAX_STORED_CONTENT = 50_000     # Store up to 50K chars of content in DB


def _get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_file_memory_db():
    """Create file memory tables if they don't exist."""
    conn = _get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS file_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            content TEXT NOT NULL,
            summary TEXT DEFAULT '',
            file_type TEXT DEFAULT '',
            file_size INTEGER DEFAULT 0,
            tags TEXT DEFAULT '[]',
            active INTEGER DEFAULT 1,
            stored_at REAL NOT NULL,
            last_accessed REAL,
            access_count INTEGER DEFAULT 0
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS file_memory_fts USING fts5(
            filename, content, summary, tags,
            content='file_memories', content_rowid='id'
        );
    """)
    conn.commit()
    conn.close()
    log.info("File memory database initialized")


def store_file_in_memory(
    filepath: str,
    tags: list[str] = None,
    summary: str = "",
) -> dict:
    """
    Read a file and store it in JARVIS memory.
    Returns {"success": bool, "id": int, "message": str}
    """
    try:
        p = Path(filepath).expanduser()
        if not p.exists():
            return {"success": False, "message": f"File not found: {filepath}"}

        file_size = p.stat().st_size
        file_type = p.suffix.lower()

        # Read content
        try:
            if file_size > MAX_FILE_SIZE_BYTES:
                # Only read first portion of very large files
                content = p.read_text(encoding="utf-8", errors="ignore")[:MAX_STORED_CONTENT]
                content += f"\n\n[File truncated — original size: {file_size:,} bytes]"
                log.info(f"Large file truncated: {p.name} ({file_size:,} bytes)")
            else:
                content = p.read_text(encoding="utf-8", errors="ignore")
                if len(content) > MAX_STORED_CONTENT:
                    content = content[:MAX_STORED_CONTENT] + "\n\n[Content truncated]"
        except UnicodeDecodeError:
            return {
                "success": False,
                "message": f"Cannot read {p.name} — binary file not supported for text memory."
            }

        conn = _get_db()
        cur = conn.execute(
            """
            INSERT INTO file_memories
            (filename, filepath, content, summary, file_type, file_size, tags, stored_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                p.name, str(p), content, summary,
                file_type, file_size,
                json.dumps(tags or []), time.time()
            )
        )
        mem_id = cur.lastrowid

        # Update FTS index
        conn.execute(
            "INSERT INTO file_memory_fts (rowid, filename, content, summary, tags) VALUES (?, ?, ?, ?, ?)",
            (mem_id, p.name, content[:10000], summary, json.dumps(tags or []))
        )
        conn.commit()
        conn.close()

        log.info(f"Stored file in memory: {p.name} (id={mem_id}, {file_size:,} bytes)")
        return {
            "success": True,
            "id": mem_id,
            "filename": p.name,
            "message": f"Stored {p.name} in memory, sir. I'll keep it in mind for our tasks."
        }

    except Exception as e:
        log.error(f"Failed to store file: {e}")
        return {"success": False, "message": f"Failed to store file: {e}"}


def recall_file_memory(query: str, limit: int = 3) -> list[dict]:
    """Search stored file memories by content or filename."""
    words = [w for w in query.replace("'", "").split() if len(w) > 2]
    if not words:
        return []
    fts_query = " OR ".join(words[:5])

    conn = _get_db()
    try:
        results = conn.execute(
            """
            SELECT fm.* FROM file_memory_fts f
            JOIN file_memories fm ON f.rowid = fm.id
            WHERE file_memory_fts MATCH ? AND fm.active = 1
            ORDER BY rank LIMIT ?
            """,
            (fts_query, limit)
        ).fetchall()

        for r in results:
            conn.execute(
                "UPDATE file_memories SET last_accessed=?, access_count=access_count+1 WHERE id=?",
                (time.time(), r["id"])
            )
        conn.commit()
    except Exception as e:
        log.error(f"File memory recall failed: {e}")
        results = []
    finally:
        conn.close()

    return [dict(r) for r in results]


def get_active_file_memories() -> list[dict]:
    """Get all currently active (stored) file memories."""
    conn = _get_db()
    results = conn.execute(
        "SELECT id, filename, filepath, summary, file_type, file_size, tags, stored_at "
        "FROM file_memories WHERE active=1 ORDER BY stored_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in results]


def remove_file_from_memory(file_id: int) -> dict:
    """Remove a file from JARVIS memory."""
    conn = _get_db()
    conn.execute("UPDATE file_memories SET active=0 WHERE id=?", (file_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": f"File {file_id} removed from memory."}


def build_file_context_for_prompt(user_message: str) -> str:
    """
    Search file memories relevant to the user's message and
    return formatted context for injection into the system prompt.
    """
    relevant = recall_file_memory(user_message, limit=2)
    if not relevant:
        return ""

    parts = ["STORED FILE CONTEXT (files you asked me to remember):"]
    for f in relevant:
        parts.append(f"\n--- {f['filename']} ---")
        content = f["content"]
        # Only inject first 3000 chars to keep prompt size manageable
        if len(content) > 3000:
            content = content[:3000] + "\n[...truncated...]"
        parts.append(content)

    return "\n".join(parts)


FILE_STORE_TRIGGERS = [
    "store this file",
    "remember this file",
    "keep this file in mind",
    "store in your memory",
    "remember this document",
    "keep this document",
    "save this file to memory",
    "add this file to memory",
]


def is_file_store_request(text: str) -> bool:
    """Check if user wants to store a file in memory."""
    text_lower = text.lower()
    return any(trigger in text_lower for trigger in FILE_STORE_TRIGGERS)


# Initialize on import
init_file_memory_db()
