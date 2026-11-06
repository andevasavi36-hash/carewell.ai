# CareWell Clinic – AI Healthcare Assistant & Appointment Automation

Streamlit frontend + Python backend (FastAPI-ready) + Gemini AI + RAG + Supabase/SQLite.
**Demo lo synthetic data matrame. Medical diagnosis ivvadu.**

## Features
1. AI FAQ chatbot (RAG over `data/clinic_knowledge.json`)
2. Appointment booking with validation + slot availability
3. Auto confirmation / reminder / cancellation / follow-up messages
4. Admin dashboard (password protected)
5. Safety: emergency detection + medical-advice refusal

## Structure
```
app.py                  Streamlit UI
backend/                config, database, rag, ai_service, appointments, api (FastAPI)
data/clinic_knowledge.json
supabase_schema.sql
tests/test_basic.py
```

## Run locally
```
pip install -r requirements.txt
streamlit run app.py
pytest
uvicorn backend.api:app --reload   # optional FastAPI
```

## Deploy (Streamlit Cloud)
1. Ee folder anta GitHub repo lo upload cheyyi (`.streamlit/secrets.toml` upload cheyyakudadu).
2. share.streamlit.io -> New app -> repo select -> Main file: `app.py` -> Deploy.
3. App settings -> Secrets lo `.streamlit/secrets.toml.example` content paste chesi `GEMINI_API_KEY` set cheyyi.
4. (Optional) Supabase: project create -> `supabase_schema.sql` run -> SUPABASE_URL, SUPABASE_KEY secrets add.
