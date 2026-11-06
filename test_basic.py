from datetime import date, timedelta

from backend.ai_service import answer_question
from backend.appointments import all_slots, validate
from backend.rag import KnowledgeBase


def next_weekday():
    d = date.today() + timedelta(days=1)
    while d.weekday() == 6:
        d += timedelta(days=1)
    return d.isoformat()


def good():
    return dict(patient_name="Test Patient", phone="9876543210", email="t@example.com",
                department="General Medicine", doctor="Dr. Anitha Reddy",
                appointment_date=next_weekday(), appointment_time="10:00")


def test_valid_appointment_passes():
    assert validate(good()) == []


def test_invalid_phone_rejected():
    d = good(); d["phone"] = "12345"
    assert any("mobile" in e for e in validate(d))


def test_past_date_rejected():
    d = good(); d["appointment_date"] = (date.today() - timedelta(days=2)).isoformat()
    assert any("past" in e for e in validate(d))


def test_lunch_slot_rejected():
    assert "13:00" not in all_slots()
    d = good(); d["appointment_time"] = "13:00"
    assert validate(d)


def test_wrong_doctor_department():
    d = good(); d["doctor"] = "Dr. Ravi Teja"
    assert validate(d)


def test_rag_finds_timings():
    hits = KnowledgeBase().search("What are the clinic timings?")
    assert hits and hits[0]["doc"]["id"] == "hours"


def test_medical_advice_refused(monkeypatch):
    r = answer_question("Which medicine should I take for fever?")
    assert r["mode"] == "refused"


def test_emergency_detected():
    assert answer_question("I have chest pain")["mode"] == "emergency"


def test_unknown_question_says_no_info(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    r = answer_question("Do you offer helicopter rides to the clinic?")
    assert r["mode"] in ("no_info", "gemini")
