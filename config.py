"""Central config. Secrets Streamlit secrets nundi leda environment variables nundi vastayi."""
import os


def get_secret(key: str, default=None):
    try:
        import streamlit as st

        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, default)


CLINIC = {
    "name": "CareWell Clinic",
    "phone": "+91 98765 43210",
    "emergency": "108",
    "email": "hello@carewellclinic.example",
    "address": "12-4-56, Main Road, Karimnagar, Telangana 505001",
}
