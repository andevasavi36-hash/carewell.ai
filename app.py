"""CareWell Clinic - AI Healthcare Assistant & Appointment Automation (Streamlit frontend)."""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from backend.ai_service import ai_mode, answer_question
from backend.appointments import DEPARTMENTS, STATUSES, available_slots, book_appointment, send_followup
from backend.config import CLINIC, get_secret
from backend.database import get_store

st.set_page_config(page_title="CareWell Clinic AI Assistant", page_icon="🩺", layout="wide")

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:wght@600;700&family=Inter:wght@400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
h1, h2, h3 { font-family: 'Fraunces', serif !important; color: #0F3D3E; letter-spacing: -0.01em; }
.block-container { padding-top: 2rem; max-width: 1100px; }
.hero { background: #0F3D3E; color: #F6F8F5; padding: 1.6rem 1.8rem; border-radius: 14px; margin-bottom: 1.2rem; }
.hero h1 { color: #F6F8F5 !important; margin: 0 0 .3rem 0; font-size: 2rem; }
.hero p { margin: 0; opacity: .85; }
.notice { background: #FFF4DC; border-left: 4px solid #D9A441; padding: .6rem .9rem; border-radius: 6px; font-size: .9rem; }
.msgbox { background: #fff; border: 1px solid #CFE0DA; border-radius: 10px; padding: 1rem; }
</style>
""",
    unsafe_allow_html=True,
)

store = get_store()

with st.sidebar:
    st.markdown(f"### 🩺 {CLINIC['name']}")
    page = st.radio("Go to", ["AI Assistant", "Book Appointment", "Admin Dashboard"], label_visibility="collapsed")
    st.divider()
    st.caption(f"AI: {ai_mode()}")
    st.caption(f"Database: {store.name}")
    st.caption("Demo uses synthetic patient data only.")


def hero(title, sub):
    st.markdown(f'<div class="hero"><h1>{title}</h1><p>{sub}</p></div>', unsafe_allow_html=True)


# ---------------------------------------------------------------- AI Assistant
if page == "AI Assistant":
    hero("Ask about the clinic", "Timings, doctors, fees, location and policies, answered from verified clinic information.")
    st.markdown(
        '<div class="notice">This assistant shares general clinic information only. It does not give medical diagnosis or treatment advice.</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    if "chat" not in st.session_state:
        st.session_state.chat = [{"role": "assistant", "content": "Hello! Ask me about timings, doctors, fees or how to book an appointment."}]

    quick = ["What are the clinic timings?", "Which doctors are available?", "What are the consultation fees?", "How do I reschedule?"]
    cols = st.columns(len(quick))
    for c, q in zip(cols, quick):
        if c.button(q, use_container_width=True):
            st.session_state.pending_q = q

    for m in st.session_state.chat:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    prompt = st.chat_input("Type your question...") or st.session_state.pop("pending_q", None)
    if prompt:
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.spinner("Checking clinic information..."):
            res = answer_question(prompt, st.session_state.chat)
        with st.chat_message("assistant"):
            st.markdown(res["answer"])
            if res["sources"]:
                st.caption("Sources: " + ", ".join(res["sources"]))
        st.session_state.chat += [{"role": "user", "content": prompt}, {"role": "assistant", "content": res["answer"]}]

# ---------------------------------------------------------------- Booking
elif page == "Book Appointment":
    hero("Book an appointment", "Choose a doctor and a free slot. You get a confirmation message right away.")
    c1, c2 = st.columns(2)
    name = c1.text_input("Patient name")
    phone = c2.text_input("Mobile number", placeholder="10-digit number")
    email = c1.text_input("Email (optional)")
    reason = c2.text_input("Reason for visit (optional)")
    dept = c1.selectbox("Department", list(DEPARTMENTS))
    doctor = c2.selectbox("Doctor", DEPARTMENTS[dept])
    d = c1.date_input("Date", min_value=date.today(), max_value=date.today() + timedelta(days=60))
    slots = available_slots(doctor, d.isoformat()) if d.weekday() != 6 else []
    if d.weekday() == 6:
        c2.warning("Clinic is closed on Sundays.")
    elif not slots:
        c2.warning("No free slots on this date. Choose another date.")
    time_slot = c2.selectbox("Time slot", slots) if slots else None

    if st.button("Book appointment", type="primary", disabled=not slots):
        ok, errors, record, msg = book_appointment(
            dict(patient_name=name, phone=phone, email=email, department=dept, doctor=doctor,
                 appointment_date=d.isoformat(), appointment_time=time_slot, reason=reason)
        )
        if ok:
            st.success(f"Appointment booked. Reference: {record['id']}")
            st.markdown(f'<div class="msgbox"><b>Confirmation message</b><br>{msg}</div>', unsafe_allow_html=True)
        else:
            for e in errors:
                st.error(e)

# ---------------------------------------------------------------- Admin
else:
    hero("Admin dashboard", "Manage appointments and patient communication.")
    admin_pw = get_secret("ADMIN_PASSWORD", "admin123")
    if not st.session_state.get("admin_ok"):
        pw = st.text_input("Admin password", type="password")
        if st.button("Sign in"):
            if pw == admin_pw:
                st.session_state.admin_ok = True
                st.rerun()
            else:
                st.error("Wrong password.")
        st.caption("Demo default password: admin123 (change it using the ADMIN_PASSWORD secret).")
        st.stop()

    try:
        rows = store.list_appointments()
    except Exception as exc:
        st.error(f"Database error: {exc}")
        st.stop()
    df = pd.DataFrame(rows)

    m1, m2, m3, m4 = st.columns(4)
    count = lambda s: int((df["status"] == s).sum()) if not df.empty else 0
    m1.metric("Total", len(df))
    m2.metric("Pending", count("Pending"))
    m3.metric("Confirmed", count("Confirmed"))
    m4.metric("Cancelled", count("Cancelled"))

    tab1, tab2, tab3 = st.tabs(["Appointments", "Send message", "Message log"])

    with tab1:
        if df.empty:
            st.info("No appointments yet. Book one from the Book Appointment page.")
        else:
            flt = st.multiselect("Filter by status", STATUSES, default=STATUSES)
            view = df[df["status"].isin(flt)].drop(columns=["created_at"], errors="ignore")
            st.dataframe(view, use_container_width=True, hide_index=True)
            st.download_button("Download CSV", df.to_csv(index=False), "appointments.csv", "text/csv")

            st.markdown("##### Update status")
            labels = {f"{r['patient_name']} | {r['appointment_date']} {r['appointment_time']} | {r['id']}": r for r in rows}
            pick = st.selectbox("Appointment", list(labels), key="status_pick")
            new_status = st.selectbox("New status", STATUSES)
            if st.button("Save status"):
                store.update_status(labels[pick]["id"], new_status)
                st.success("Status updated.")
                st.rerun()

    with tab2:
        if df.empty:
            st.info("Nothing to message yet.")
        else:
            labels2 = {f"{r['patient_name']} | {r['appointment_date']} {r['appointment_time']} | {r['id']}": r for r in rows}
            pick2 = st.selectbox("Appointment", list(labels2), key="msg_pick")
            kind = st.selectbox("Message type", ["confirmation", "reminder", "cancellation", "followup"])
            if st.button("Generate message"):
                with st.spinner("Writing message..."):
                    text = send_followup(labels2[pick2], kind)
                st.text_area("Generated message (also saved in log)", text, height=140)

    with tab3:
        msgs = store.list_messages()
        if msgs:
            st.dataframe(pd.DataFrame(msgs), use_container_width=True, hide_index=True)
        else:
            st.info("No messages generated yet.")

    if st.button("Sign out"):
        st.session_state.admin_ok = False
        st.rerun()
