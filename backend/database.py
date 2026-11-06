"""Storage layer: Supabase if configured, else SQLite fallback (works with zero setup)."""
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import get_secret

DB_PATH = Path(__file__).resolve().parent.parent / "clinic.db"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SQLiteStore:
    name = "SQLite (local)"

    def __init__(self, path=DB_PATH):
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self.lock:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS appointments (
                    id TEXT PRIMARY KEY, patient_name TEXT, phone TEXT, email TEXT,
                    department TEXT, doctor TEXT, appointment_date TEXT,
                    appointment_time TEXT, reason TEXT, status TEXT, created_at TEXT);
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY, appointment_id TEXT, kind TEXT,
                    content TEXT, created_at TEXT);
                """
            )
            self.conn.commit()

    def add_appointment(self, data: dict) -> dict:
        rec = {
            "id": uuid.uuid4().hex[:8],
            "email": "",
            "reason": "",
            "status": "Pending",
            "created_at": _now(),
            **data,
        }
        with self.lock:
            self.conn.execute(
                "INSERT INTO appointments VALUES (:id,:patient_name,:phone,:email,:department,"
                ":doctor,:appointment_date,:appointment_time,:reason,:status,:created_at)",
                rec,
            )
            self.conn.commit()
        return rec

    def list_appointments(self) -> list:
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM appointments ORDER BY appointment_date DESC, appointment_time DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def update_status(self, appt_id: str, status: str):
        with self.lock:
            self.conn.execute("UPDATE appointments SET status=? WHERE id=?", (status, appt_id))
            self.conn.commit()

    def booked_slots(self, doctor: str, date_str: str) -> list:
        with self.lock:
            rows = self.conn.execute(
                "SELECT appointment_time FROM appointments WHERE doctor=? AND appointment_date=? "
                "AND status!='Cancelled'",
                (doctor, date_str),
            ).fetchall()
        return [r[0] for r in rows]

    def add_message(self, appt_id: str, kind: str, content: str):
        with self.lock:
            self.conn.execute(
                "INSERT INTO messages VALUES (?,?,?,?,?)",
                (uuid.uuid4().hex[:8], appt_id, kind, content, _now()),
            )
            self.conn.commit()

    def list_messages(self) -> list:
        with self.lock:
            rows = self.conn.execute("SELECT * FROM messages ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


class SupabaseStore:
    name = "Supabase"

    def __init__(self, url: str, key: str):
        from supabase import create_client

        self.client = create_client(url, key)
        # Tables unnaya ani verify cheyyadam (lekapothe exception -> SQLite fallback)
        self.client.table("appointments").select("id").limit(1).execute()
        self.client.table("messages").select("id").limit(1).execute()

    def add_appointment(self, data: dict) -> dict:
        rec = {"email": "", "reason": "", "status": "Pending", **data}
        res = self.client.table("appointments").insert(rec).execute()
        return res.data[0]

    def list_appointments(self) -> list:
        res = (
            self.client.table("appointments")
            .select("*")
            .order("appointment_date", desc=True)
            .order("appointment_time", desc=True)
            .execute()
        )
        return res.data

    def update_status(self, appt_id: str, status: str):
        self.client.table("appointments").update({"status": status}).eq("id", appt_id).execute()

    def booked_slots(self, doctor: str, date_str: str) -> list:
        res = (
            self.client.table("appointments")
            .select("appointment_time")
            .eq("doctor", doctor)
            .eq("appointment_date", date_str)
            .neq("status", "Cancelled")
            .execute()
        )
        return [r["appointment_time"] for r in res.data]

    def add_message(self, appt_id: str, kind: str, content: str):
        self.client.table("messages").insert(
            {"appointment_id": str(appt_id), "kind": kind, "content": content}
        ).execute()

    def list_messages(self) -> list:
        res = self.client.table("messages").select("*").order("created_at", desc=True).execute()
        return res.data


SEED = [
    ("Ravi Kumar", "9876500001", "ravi.demo@example.com", "General Medicine", "Dr. Anitha Reddy", 1, "10:00", "Seasonal fever follow-up", "Confirmed"),
    ("Sneha Reddy", "9876500002", "sneha.demo@example.com", "Dermatology", "Dr. Ravi Teja", 2, "11:30", "Skin allergy consultation", "Pending"),
    ("Arjun Varma", "9876500003", "arjun.demo@example.com", "Orthopedics", "Dr. Venkat Rao", 3, "15:00", "Knee pain review", "Pending"),
]

_store = None


def _seed_if_empty(store):
    from datetime import date, timedelta

    try:
        if store.list_appointments():
            return
        for name, phone, email, dept, doc, days, t, reason, status in SEED:
            d = date.today() + timedelta(days=days)
            if d.weekday() == 6:  # Sunday skip
                d += timedelta(days=1)
            store.add_appointment(
                dict(patient_name=name, phone=phone, email=email, department=dept, doctor=doc,
                     appointment_date=d.isoformat(), appointment_time=t, reason=reason, status=status)
            )
    except Exception:
        pass


def get_store():
    global _store
    if _store is not None:
        return _store
    url, key = get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY")
    if url and key:
        try:
            _store = SupabaseStore(url, key)
        except Exception:
            _store = SQLiteStore()
    else:
        _store = SQLiteStore()
    _seed_if_empty(_store)
    return _store
