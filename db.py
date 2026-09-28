import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "data.sqlite")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS stalls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stall_name TEXT NOT NULL,
            key_hash TEXT NOT NULL UNIQUE,
            session_token TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stall_id INTEGER NOT NULL,
            qr_code_id TEXT NOT NULL,
            amount_inr REAL NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            paid_at TEXT,
            FOREIGN KEY (stall_id) REFERENCES stalls(id)
        );
        """
    )
    conn.commit()
    conn.close()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def create_stall(stall_name: str, key_hash: str) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO stalls (stall_name, key_hash, created_at) VALUES (?, ?, ?)",
        (stall_name, key_hash, now_iso()),
    )
    conn.commit()
    stall_id = cur.lastrowid
    conn.close()
    return stall_id


def list_stalls():
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, stall_name, created_at FROM stalls ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stall_by_key_hash(key_hash: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM stalls WHERE key_hash = ?", (key_hash,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_stall_by_token(token: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM stalls WHERE session_token = ?", (token,)).fetchone()
    conn.close()
    return dict(row) if row else None


def set_stall_token(stall_id: int, token: str):
    conn = get_conn()
    conn.execute("UPDATE stalls SET session_token = ? WHERE id = ?", (token, stall_id))
    conn.commit()
    conn.close()


def create_payment(stall_id: int, qr_code_id: str, amount_inr: float, description: str) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO payments (stall_id, qr_code_id, amount_inr, description, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (stall_id, qr_code_id, amount_inr, description, now_iso()),
    )
    conn.commit()
    payment_id = cur.lastrowid
    conn.close()
    return payment_id


def get_payment(payment_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_payment_by_qr_code_id(qr_code_id: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM payments WHERE qr_code_id = ?", (qr_code_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def mark_payment_paid(payment_id: int):
    conn = get_conn()
    conn.execute(
        "UPDATE payments SET status = 'paid', paid_at = ? WHERE id = ?",
        (now_iso(), payment_id),
    )
    conn.commit()
    conn.close()


def list_payments_with_stall():
    conn = get_conn()
    rows = conn.execute(
        """
         SELECT p.id AS payment_id, s.id AS stall_id, s.stall_name,
             p.amount_inr, p.description,
               p.status, p.created_at, p.paid_at
        FROM payments p JOIN stalls s ON p.stall_id = s.id
        ORDER BY p.created_at DESC
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
