# =========================
import os
import requests
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import pytz




API_BASE = "https://bapi-etail.wallmob.com"
CLIENT_ID = os.getenv("CLIENT_ID", "3eebafa89502ec44bb2c721c5316d73f")
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "din_client_secret_här")
TZ_STO = pytz.timezone("Europe/Stockholm")


def get_token():
    url = f"{API_BASE}/auth/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scopes": "public",   # viktigt: plural
    }
    r = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=30)
    st.write("DEBUG TOKEN RESPONSE:", r.status_code, r.text)  # tillfällig debug
    r.raise_for_status()
    return r.json()["access_token"]
