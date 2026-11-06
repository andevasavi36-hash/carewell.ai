"""AI layer: RAG chatbot (Gemini) + patient message generation. Works without API key (fallback mode)."""
import re

import requests

from .config import CLINIC, get_secret
from .rag import get_kb

EMERGENCY_RE = re.compile(
    r"chest pain|heart attack|can'?t breathe|cannot breathe|difficulty breathing|unconscious|"
    r"severe bleeding|stroke|suicid|overdose|emergency", re.I)
MEDICAL_ADVICE_RE = re.compile(
    r"diagnos|what disease|which disease|do i have|which medicine|what medicine|medicine for|"
    r"tablet for|dosage|dose of|prescribe|should i take|treatment for|cure for|home remed|"
    r"is it (cancer|diabetes|serious)", re.I)

SYSTEM_PROMPT = f"""You are the virtual assistant of {CLINIC['name']}.
RULES:
1. Answer ONLY using the CONTEXT provided. Do not use outside knowledge about the clinic.
2. If the answer is not in the CONTEXT, say clearly that you don't have that information and suggest calling {CLINIC['phone']}.
3. NEVER give medical diagnosis, medicine names, dosages or treatment advice. Suggest booking a consultation instead.
4. Be polite, short (max 4 sentences) and reply in the same language the user writes in.
5. In emergencies tell the user to call {CLINIC['emergency']} immediately."""

EMERGENCY_REPLY = (
    f"This sounds like it could be an emergency. Please call **{CLINIC['emergency']}** or go to the nearest "
    "hospital emergency department right now. CareWell Clinic is an outpatient clinic and cannot handle emergencies."
)
MEDICAL_REPLY = (
    "I can't give medical diagnosis or treatment advice. A doctor needs to examine you for that. "
    "I can help you **book an appointment** (use the Book Appointment page) or share clinic information such as timings, fees and doctors."
)
NO_INFO_REPLY = (
    "Sorry, I don't have that information in the clinic's verified details. "
    f"Please call us at {CLINIC['phone']} and the team will help you."
)


class AIUnavailable(Exception):
    pass


def ai_mode() -> str:
    return "Gemini connected" if get_secret("GEMINI_API_KEY") else "Fallback mode (no API key)"


def _gemini(prompt: str, system: str = None, temperature: float = 0.2) -> str:
    key = get_secret("GEMINI_API_KEY")
    if not key:
        raise AIUnavailable("GEMINI_API_KEY not set")
    model = get_secret("GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": 2048},
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    try:
        r = requests.post(url, headers={"x-goog-api-key": key}, json=body, timeout=30)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as exc:
        raise AIUnavailable(str(exc)) from exc


def answer_question(question: str, history: list = None) -> dict:
    """Returns {answer, sources, mode}. mode: emergency | refused | gemini | fallback | no_info."""
    question = (question or "").strip()
    if not question:
        return {"answer": "Please type your question.", "sources": [], "mode": "empty"}
    if EMERGENCY_RE.search(question):
        return {"answer": EMERGENCY_REPLY, "sources": [], "mode": "emergency"}
    if MEDICAL_ADVICE_RE.search(question):
        return {"answer": MEDICAL_REPLY, "sources": [], "mode": "refused"}

    hits = get_kb().search(question, k=4)
    sources = [h["doc"]["title"] for h in hits]

    if get_secret("GEMINI_API_KEY"):
        context = "\n\n".join(f"[{h['doc']['title']}]\n{h['doc']['text']}" for h in hits) or "(no matching information)"
        convo = ""
        for m in (history or [])[-6:]:
            convo += f"{m['role'].upper()}: {m['content']}\n"
        prompt = f"CONTEXT:\n{context}\n\nCONVERSATION SO FAR:\n{convo}\nUSER QUESTION: {question}"
        try:
            return {"answer": _gemini(prompt, SYSTEM_PROMPT), "sources": sources, "mode": "gemini"}
        except AIUnavailable:
            pass  # fallback below

    if hits and hits[0]["coverage"] >= 0.5:
        return {"answer": hits[0]["doc"]["text"], "sources": sources[:1], "mode": "fallback"}
    return {"answer": NO_INFO_REPLY, "sources": [], "mode": "no_info"}


def _template(kind: str, a: dict) -> str:
    base = f"{a['doctor']} ({a['department']}) on {a['appointment_date']} at {a['appointment_time']}"
    t = {
        "confirmation": f"Hello {a['patient_name']}, your appointment with {base} is booked at {CLINIC['name']}. "
                        f"Please arrive 10 minutes early. To reschedule call {CLINIC['phone']}.",
        "reminder": f"Reminder: {a['patient_name']}, you have an appointment with {base}. "
                    f"Please bring your ID and previous reports. Call {CLINIC['phone']} to reschedule.",
        "cancellation": f"Hello {a['patient_name']}, your appointment with {base} has been cancelled. "
                        f"You can book a new slot anytime on our website or call {CLINIC['phone']}.",
        "followup": f"Hello {a['patient_name']}, thank you for visiting {CLINIC['name']}. We hope you are doing well. "
                    f"If you need a follow-up visit, please book a slot or call {CLINIC['phone']}.",
    }
    return t[kind]


def generate_patient_message(kind: str, appt: dict) -> str:
    """kind: confirmation | reminder | cancellation | followup. AI polish if key available else template."""
    draft = _template(kind, appt)
    if not get_secret("GEMINI_API_KEY"):
        return draft
    prompt = (
        f"Rewrite this {kind} message for a clinic patient. Keep ALL facts (name, doctor, date, time, phone) exactly. "
        "Professional, warm, under 60 words, plain text, no medical advice.\n\n" + draft
    )
    try:
        return _gemini(prompt, temperature=0.4)
    except AIUnavailable:
        return draft
