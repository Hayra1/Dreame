import os
import requests
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv  # <-- NEW

load_dotenv()  # <-- NEW: läs .env

# =========================
# Konfiguration
# =========================
API_BASE = os.getenv("EXTENDA_BASE_URL", "https://bapi-etail.wallmob.com")
CLIENT_ID = os.getenv("EXTENDA_CLIENT_ID")
CLIENT_SECRET = os.getenv("EXTENDA_CLIENT_SECRET")
TZ_STO = pytz.timezone("Europe/Stockholm")

# =========================
# Hjälpfunktioner
# =========================
def get_token():
    url = f"{API_BASE}/auth/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scopes": "public"
    }
    r = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=30
    )
    r.raise_for_status()
    return r.json().get("access_token")


def fetch_turnover(token, starttime, endtime, shop_id=None, interval_grouping=3600):
    headers = {"Authorization": f"Bearer {token}"}

    # Shop-specific först
    if shop_id:
        url = f"{API_BASE}/shops/{shop_id}/turnover"
        params = {"starttime": starttime, "endtime": endtime, "interval_grouping": interval_grouping}
        r = requests.get(url, headers=headers, params=params, timeout=30)
        if r.status_code == 500:
            # Fallback till global turnover
            url = f"{API_BASE}/turnover"
            params = {"starttime": starttime, "endtime": endtime, "interval_grouping": interval_grouping}
            r = requests.get(url, headers=headers, params=params, timeout=30)
    else:
        url = f"{API_BASE}/turnover"
        params = {"starttime": starttime, "endtime": endtime, "interval_grouping": interval_grouping}
        r = requests.get(url, headers=headers, params=params, timeout=30)

    r.raise_for_status()
    return r.json()


def fetch_category_sales(token, starttime, endtime, shop_id=None):
    url = f"{API_BASE}/category_sales"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"starttime": starttime, "endtime": endtime}
    if shop_id:
        params["shopid"] = shop_id  # <- viktigt: INTE shop_id
    r = requests.get(url, headers=headers, params=params, timeout=30)
    if r.status_code == 500:
        # en del instanser svarar 500 när ingen data finns
        return []
    r.raise_for_status()
    return r.json()

def fetch_tender_sales(token, starttime, endtime):
    url = f"{API_BASE}/tender_type_sales"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"starttime": starttime, "endtime": endtime}
    r = requests.get(url, headers=headers, params=params, timeout=30)
    if r.status_code == 500:
        return []
    r.raise_for_status()
    return r.json()

# =========================
# Streamlit App
# =========================
st.set_page_config(page_title="Försäljningsdashboard", layout="wide")

st.title("📊 Dagens Försäljning")

# Datum-intervall för idag
now = datetime.now(TZ_STO)
start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
end_dt = now
starttime = int(start_dt.timestamp())
endtime = int(end_dt.timestamp())

# Hämta access token
if "access_token" not in st.session_state:
    st.session_state["access_token"] = get_token()
token = st.session_state["access_token"]

# Shop ID (hårdkodad om ni vill)
SHOP_ID = "709a1ed9-8fcc-4854-e516-726b4c404f52"

# =========================
# Hämta data
# =========================
turnover_raw = fetch_turnover(token, starttime, endtime, SHOP_ID)
cats_raw = fetch_category_sales(token, starttime, endtime, SHOP_ID)
tenders_raw = fetch_tender_sales(token, starttime, endtime)

# =========================
# Processa turnover-data
# =========================
buckets = turnover_raw if isinstance(turnover_raw, list) else []

total_sales = sum(int(b.get("turnover", 0)) for b in buckets) / 100.0
order_count = sum(int(b.get("order_count", 0)) for b in buckets)
avg_order = (total_sales / order_count) if order_count else 0.0
goal = 20000
goal_pct = (total_sales / goal * 100) if goal > 0 else 0.0

# KPI-rad
c1, c2, c3, c4 = st.columns(4)
c1.metric("Totalförsäljning idag", f"{total_sales:,.0f} kr")
c2.metric("Antal köp", f"{order_count:,}")
c3.metric("Snittköp", f"{avg_order:,.0f} kr")
c4.metric("Måluppfyllelse", f"{goal_pct:.1f} %")

st.progress(min(goal_pct / 100, 1.0))

# =========================
# Försäljning per timme
# =========================
st.subheader("Försäljning per timme")

if buckets:
    df = pd.DataFrame([
        {
            "interval_index": int(b.get("intervals_since_start", 0)),
            "turnover_sek": int(b.get("turnover", 0)) / 100.0,
            "order_count": int(b.get("order_count", 0)),
        }
        for b in buckets
    ])

    # Bygg timetiketter
    df["hour_label"] = df["interval_index"].apply(
        lambda idx: (start_dt + timedelta(hours=idx)).strftime("%H:%M")
    )

    # Fyll luckor
    all_hours = pd.date_range(start=start_dt, end=end_dt, freq="H", tz=TZ_STO)
    df_all = pd.DataFrame({"hour_label": all_hours.strftime("%H:%M")})
    df_filled = df_all.merge(
        df[["hour_label", "turnover_sek", "order_count"]],
        on="hour_label",
        how="left",
    ).fillna({"turnover_sek": 0.0, "order_count": 0})

    chart = (
        alt.Chart(df_filled)
        .mark_bar()
        .encode(
            x=alt.X("hour_label:N", title="Timme"),
            y=alt.Y("turnover_sek:Q", title="Omsättning (kr)"),
            tooltip=[
                alt.Tooltip("hour_label:N", title="Timme"),
                alt.Tooltip("turnover_sek:Q", title="Omsättning (kr)", format=",.0f"),
                alt.Tooltip("order_count:Q", title="Antal köp"),
            ],
        )
        .properties(height=300)
    )
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("Ingen försäljningsdata per timme tillgänglig.")

# =========================
# Mest sålda kategorier
# =========================
st.subheader("Mest sålda kategorier idag")

if cats_raw:
    df_cats = pd.DataFrame(cats_raw)
    df_cats["turnover_sek"] = df_cats["turnover"].astype(int) / 100.0
    st.bar_chart(df_cats.set_index("category_name")["turnover_sek"])
else:
    st.info("Ingen kategoriförsäljning tillgänglig för idag.")

# =========================
# Försäljning per betalsätt
# =========================
st.subheader("Försäljning per betalsätt")

if tenders_raw:
    df_tenders = pd.DataFrame(tenders_raw)
    df_tenders["turnover_sek"] = df_tenders["turnover"].astype(int) / 100.0
    st.bar_chart(df_tenders.set_index("tender_type")["turnover_sek"])
else:
    st.info("Ingen betalmedelsdata tillgänglig för idag.")

# =========================
# Debug
# =========================
with st.expander("🔎 Debug (klicka för detaljer)"):
    st.write("start_dt:", start_dt, "→ UNIX:", starttime)
    st.write("end_dt:", end_dt, "→ UNIX:", endtime)
    st.write("TURNOVER raw:", turnover_raw)
    st.write("CATS raw:", cats_raw)
    st.write("TENDERS raw:", tenders_raw)


