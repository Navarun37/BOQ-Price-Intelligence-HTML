"""BOQ Price Finder — Streamlit ที่แสดงหน้า HTML เดิม 100%

หลักการ: BOQ_price_finder.html เป็นไฟล์เดี่ยวสมบูรณ์ในตัว
(ข้อมูล OBEC 2,061 รายการ + fflate + CSS/JS ฝังครบ ไม่ต้องมี backend)
จึงอ่านไฟล์แล้วฝังทั้งหน้าเต็มจอด้วย st.components.v1.html
— ได้หน้าเดิมเป๊ะทุก pixel ทุกฟีเจอร์ (ค้นราคา / Library / Fill BOQ / Export)
และใช้ได้ทั้งรันในเครื่องและ deploy บน Streamlit Cloud โดยไม่ต้องเปิดพอร์ตเพิ่ม

เวอร์ชัน UI แบบ Streamlit widgets เก็บไว้ที่ streamlit_app_widgets.py

รัน:  streamlit run streamlit_app.py
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

HTML_FILE = Path(__file__).parent / "BOQ_price_finder.html"

st.set_page_config(
    page_title="BOQ Price Finder",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_data
def load_html() -> str:
    return HTML_FILE.read_text(encoding="utf-8")


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

components.html(load_html(), height=900, scrolling=True)
