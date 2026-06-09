import json, re, pathlib, datetime
import streamlit as st
import streamlit.components.v1 as components
import usda_fetch

st.set_page_config(page_title="TGFC TGFC Market Dashboard",
                   layout="wide", initial_sidebar_state="collapsed")
HERE = pathlib.Path(__file__).parent

@st.cache_data(ttl=6 * 3600, show_spinner="Fetching the latest USDA market data…")
def load_data():
    baseline = json.loads((HERE / "baseline_data.json").read_text())
    return usda_fetch.build_data(baseline)

st.sidebar.markdown("### TGFC Dashboard")
version = st.sidebar.radio("Version", ["TGFC branded", "Plain / original"], index=0)
if st.sidebar.button("↻ Force refresh now"):
    load_data.clear()
data = load_data()

tmpl = "template_branded.html" if version.startswith("TGFC") else "template_plain.html"
html = (HERE / tmpl).read_text(encoding="utf-8")
html = re.sub(r"const DATA = \{[\s\S]*?\};", "const DATA = " + json.dumps(data) + ";", html, count=1)
components.html(html, height=5600, scrolling=True)

st.sidebar.caption("Data refreshes automatically every 6 hours, pulling live from "
                   "USDA AMS / NASS / FAS. Any report that can't be read falls back "
                   "to the last good snapshot.")
st.sidebar.caption("Last load: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
st.sidebar.write({"source status": data.get("_status", {})})
