"""Appointment business logic: validation, slot generation, booking + automated messages."""
import re
from datetime import date, datetime, time, timedelta

from .ai_service import generate_patient_message
from .database import get_store

DEPARTMENTS = {
    "General Medicine": ["Dr. Anitha Reddy", "Dr. Suresh Kumar"],
    "Pediatrics": ["Dr. Lakshmi Prasad"],
    "Dermatology": ["Dr. Ravi Teja"],
    "Orthopedics": ["Dr. Venkat Rao"],
    "Gynecology": ["Dr. Swathi Naidu"],
}
STATUSES = ["Pending", "Confirmed", "Completed", "Cancelled"]
PHONE_RE = re.compile(r"^(\+91[\-\s]?)?[6-9]\d{9}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def all_slots():
    """09:00 - 16:30, 30-min slots, lunch 13:00-14:00 skip."""
    slots, cur = [], datetime.combine(date.today(), time(9, 0))
    end = datetime.combine(date.today(), time(17, 0))
    while cur < end:
        if not (time(13, 0) <= cur.time() < time(14, 0)):
            slots.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=30)
    return slots


def available_slots(doctor: str, date_str: str):
    taken = set(get_store().booked_slots(doctor, date_str))
    slots = [s for s in all_slots() if s not in taken]
    if date_str == date.today().isoformat():
        now = datetime.now().strftime("%H:%M")
        slots = [s for s in slots if s > now]
    return slots


def validate(data: dict) -> list:
    errors = []
    name = (data.get("patient_name") or "").strip()
    if len(name) < 2 or not re.match(r"^[A-Za-z .'\-]+$", name):
        errors.append("Enter a valid patient name (letters only, minimum 2 characters).")
    if not PHONE_RE.match((data.get("phone") or "").strip()):
        errors.append("Enter a valid 10-digit Indian mobile number.")
    email = (data.get("email") or "").strip()
    if email and not EMAIL_RE.match(email):
        errors.append("Email address format is invalid.")
    dept, doctor = data.get("department"), data.get("doctor")
    if dept not in DEPARTMENTS:
        errors.append("Select a valid department.")
    elif doctor not in DEPARTMENTS[dept]:
        errors.append("Selected doctor does not belong to this department.")
    try:
        d = datetime.strptime(str(data.get("appointment_date")), "%Y-%m-%d").date()
        if d < date.today():
            errors.append("Appointment date cannot be in the past.")
        elif d.weekday() == 6:
            errors.append("The clinic is closed on Sundays. Choose another date.")
    except ValueError:
        errors.append("Select a valid appointment date.")
    if data.get("appointment_time") not in all_slots():
        errors.append("Select a valid time slot (9:00 AM - 5:00 PM, no lunch hour).")
    return errors


def book_appointment(data: dict):
    """Returns (ok, errors, record, confirmation_message)."""
    data = {k: (v.strip() if isinstance(v, str) else v) for k, v in data.items()}
    errors = validate(data)
    if errors:
        return False, errors, None, None
    store = get_store()
    try:
        if data["appointment_time"] in store.booked_slots(data["doctor"], data["appointment_date"]):
            return False, ["That slot was just booked. Please choose another time."], None, None
        record = store.add_appointment(data)
    except Exception as exc:  # database failure
        return False, [f"Could not save the appointment right now ({type(exc).__name__}). Please try again."], None, None
    message = generate_patient_message("confirmation", record)
    try:
        store.add_message(record["id"], "confirmation", message)
    except Exception:
        pass
    return True, [], record, message


def send_followup(appt: dict, kind: str) -> str:
    message = generate_patient_message(kind, appt)
    get_store().add_message(appt["id"], kind, message)
    return message
