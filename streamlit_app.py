"""BOQ Price Finder — Streamlit wrapper แสดงหน้า BOQ_price_finder.html เดิม 100%

ตัวไฟล์นี้เป็น wrapper ง่าย ๆ เท่านั้น: อ่าน BOQ_price_finder.html
(ไฟล์เดี่ยวสมบูรณ์ในตัว) แล้วฝังเต็มจอด้วย st.components.v1.html

ส่วนดึงราคาสด (/api/search) แยกอยู่ที่ live_api.py และต่อแบบ optional —
ถ้าติดตั้งไม่สำเร็จ แอปไม่ crash หน้าเว็บแค่ค้นจากข้อมูล สพฐ. ที่ฝังในไฟล์แทน

เวอร์ชัน UI แบบ Streamlit widgets เก็บไว้ที่ streamlit_app_widgets.py

รัน:  streamlit run streamlit_app.py
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

HTML_FILE = Path(__file__).parent / "BOQ_price_finder.html"
PROTOCOL_CHECK = "return location.protocol === 'http:' || location.protocol === 'https:';"

st.set_page_config(
    page_title="BOQ Price Finder",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_resource
def setup_live_search() -> bool:
    """เปิด /api/search ถ้าทำได้ — ล้มเหลวเมื่อไรก็ตกไปโหมด offline เฉย ๆ"""
    try:
        from live_api import install_search_api
        return install_search_api()
    except Exception:
        return False


@st.cache_data
def load_html(live: bool) -> str:
    html = HTML_FILE.read_text(encoding="utf-8")
    if live:
        # srcdoc iframe มี protocol เป็น about: -> เปิดทางเรียก live backend
        # (ถ้าเรียกไม่สำเร็จ โค้ดในหน้า fallback ไปค้นข้อมูลฝังในไฟล์เอง)
        html = html.replace(PROTOCOL_CHECK, "return true;", 1)
    return html


live_ready = setup_live_search()

# ซ่อน chrome ของ Streamlit ทั้งหมด และยืด iframe ให้เต็มจอ
st.markdown(
    """
    <style>
      header[data-testid="stHeader"], footer, [data-testid="stSidebar"],
      [data-testid="stSidebarCollapsedControl"] { display: none !important; }
      .stApp { background: #f8f9ff; }
      .block-container, [data-testid="stMainBlockContainer"] {
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100% !important;
      }
      [data-testid="stVerticalBlock"] { gap: 0 !important; }
      div[data-testid="stIFrame"] iframe,
      iframe[title="st.iframe"] {
        width: 100% !important;
        height: 100vh !important;
        border: none;
        display: block;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

components.html(load_html(live_ready), height=900, scrolling=True)
