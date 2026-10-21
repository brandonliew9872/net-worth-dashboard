"""Private, read-only Streamlit test of the Supabase portfolio_nav REST API."""
import hmac
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Supabase Connection Test", page_icon="🔒", layout="wide")

REQUIRED = ("SUPABASE_URL", "SUPABASE_SECRET_KEY", "DASHBOARD_PASSWORD")
missing = [name for name in REQUIRED if not st.secrets.get(name)]
if missing:
    st.error("Missing Streamlit secrets: " + ", ".join(missing))
    st.stop()

if not st.session_state.get("authenticated", False):
    st.title("🔒 Private NAV Dashboard")
    with st.form("login"):
        password = st.text_input("Dashboard password", type="password")
        submitted = st.form_submit_button("Unlock")
    if submitted:
        if hmac.compare_digest(password, str(st.secrets["DASHBOARD_PASSWORD"])):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password")
    st.stop()

st.title("Supabase → Streamlit Test")
if st.button("Log out"):
    st.session_state.authenticated = False
    st.rerun()

# Use a server-side privileged key ONLY after checking the session password.
# Never send the key to the browser or print it in logs.
url = str(st.secrets["SUPABASE_URL"]).rstrip("/") + "/rest/v1/portfolio_nav"
key = str(st.secrets["SUPABASE_SECRET_KEY"])
headers = {"apikey": key, "Accept": "application/json"}
if not key.startswith("sb_secret_"):
    headers["Authorization"] = "Bearer " + key

try:
    response = requests.get(
        url,
        headers=headers,
        params={"select": "platform,recorded_at,nav_original,original_currency,nav_usd",
                "platform": "eq.luno", "order": "recorded_at.asc", "limit": "1000"},
        timeout=20,
    )
    if not response.ok:
        # Don't show the response body; it may contain sensitive details.
        st.error(f"Supabase returned HTTP {response.status_code}. Check URL, key and table access.")
        st.stop()
    rows = response.json()
    if not isinstance(rows, list):
        st.error("Unexpected response from Supabase")
        st.stop()
except requests.RequestException:
    st.error("Could not reach Supabase. Check the Project URL and connection.")
    st.stop()

if not rows:
    st.warning("Connection succeeded, but no Luno records were found yet.")
    st.stop()

df = pd.DataFrame(rows)
df["recorded_at"] = pd.to_datetime(df["recorded_at"], utc=True, errors="coerce")
for column in ("nav_original", "nav_usd"):
    df[column] = pd.to_numeric(df[column], errors="coerce")
df = df.dropna(subset=["recorded_at", "nav_original", "nav_usd"]).sort_values("recorded_at")
if df.empty:
    st.error("Records exist, but none had valid timestamps and NAV amounts.")
    st.stop()

latest = df.iloc[-1]
st.success(f"Connected to Supabase: {len(df)} Luno NAV record(s) loaded.")
c1, c2, c3 = st.columns(3)
c1.metric("Latest Luno NAV (MYR)", f"RM {latest['nav_original']:,.2f}")
c2.metric("Latest Luno NAV (USD)", f"$ {latest['nav_usd']:,.2f}")
c3.metric("Stored records", len(df))
st.caption("Last record: " + latest["recorded_at"].tz_convert("Asia/Kuala_Lumpur").strftime("%d %b %Y, %I:%M %p MYT"))
st.subheader("Luno USD NAV history")
chart = df.set_index("recorded_at")[["nav_usd"]]
st.line_chart(chart)
st.subheader("Saved Luno NAV records")
st.dataframe(df.sort_values("recorded_at", ascending=False), hide_index=True, use_container_width=True)
