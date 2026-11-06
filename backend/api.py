"""Optional FastAPI backend. Run locally:  uvicorn backend.api:app --reload
(Streamlit app same backend modules ni directly use chestundi, so Streamlit Cloud lo separate server avasaram ledu.)"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .ai_service import ai_mode, answer_question
from .appointments import STATUSES, book_appointment, send_followup
from .database import get_store

app = FastAPI(title="CareWell Clinic API", version="1.0")


class ChatIn(BaseModel):
    question: str
    history: list = []


class AppointmentIn(BaseModel):
    patient_name: str
    phone: str
    email: str = ""
    department: str
    doctor: str
    appointment_date: str  # YYYY-MM-DD
    appointment_time: str  # HH:MM
    reason: str = ""


class StatusIn(BaseModel):
    status: str


@app.get("/health")
def health():
    return {"status": "ok", "ai": ai_mode(), "database": get_store().name}


@app.post("/chat")
def chat(body: ChatIn):
    return answer_question(body.question, body.history)


@app.post("/appointments")
def create_appointment(body: AppointmentIn):
    ok, errors, record, message = book_appointment(body.model_dump())
    if not ok:
        raise HTTPException(status_code=422, detail=errors)
    return {"appointment": record, "confirmation_message": message}


@app.get("/appointments")
def list_appointments():
    return get_store().list_appointments()


@app.patch("/appointments/{appt_id}/status")
def update_status(appt_id: str, body: StatusIn):
    if body.status not in STATUSES:
        raise HTTPException(status_code=422, detail=f"Status must be one of {STATUSES}")
    get_store().update_status(appt_id, body.status)
    return {"id": appt_id, "status": body.status}


@app.post("/appointments/{appt_id}/message/{kind}")
def message(appt_id: str, kind: str):
    appt = next((a for a in get_store().list_appointments() if str(a["id"]) == appt_id), None)
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if kind not in ("confirmation", "reminder", "cancellation", "followup"):
        raise HTTPException(status_code=422, detail="Invalid message kind")
    return {"message": send_followup(appt, kind)}
