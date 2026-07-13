"""BOQ Price Finder — Streamlit ที่แสดงหน้า HTML เดิม 100% + ดึงราคาสด

หลักการ:
1) ฝัง BOQ_price_finder.html (ไฟล์เดี่ยวสมบูรณ์ในตัว) เต็มจอด้วย
   st.components.v1.html — ได้หน้าเดิมเป๊ะทุก pixel ทุกฟีเจอร์
2) เพิ่ม endpoint /api/search เข้าไปใน Tornado server ของ Streamlit เอง
   (โปรเซสเดียว พอร์ตเดียว — ใช้ได้ทั้งรันในเครื่องและบน Streamlit Cloud)
   โดยเรียก run_search() จาก server.py เพื่อดึงราคาสดจากเว็บร้านตอน user ค้นหา
3) แก้ canUseLiveBackend() ใน HTML ที่ฝังให้ลองเรียก live backend เสมอ
   (ถ้าเรียกไม่สำเร็จ โค้ดเดิมใน HTML จะ fallback ไปค้นข้อมูล สพฐ. ที่ฝังในไฟล์เอง)

เวอร์ชัน UI แบบ Streamlit widgets เก็บไว้ที่ streamlit_app_widgets.py

รัน:  streamlit run streamlit_app.py
"""
from __future__ import annotations

import asyncio
import gc
import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
import tornado.web

HTML_FILE = Path(__file__).parent / "BOQ_price_finder.html"
PROTOCOL_CHECK = "return location.protocol === 'http:' || location.protocol === 'https:';"

st.set_page_config(
    page_title="BOQ Price Finder",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_resource
def install_search_api() -> bool:
    """เพิ่ม /api/search เข้า Tornado app ของ Streamlit (ครั้งเดียวต่อโปรเซส)

    หน้า HTML ที่ฝังเป็น srcdoc iframe ซึ่ง base URL ชี้กลับมาที่ origin ของ
    Streamlit เอง fetch('/api/search?…') จึงวิ่งเข้า handler นี้โดยตรง
    """
    from server import run_search  # scraper เดิมใน server.py ไม่แตะต้อง

    class SearchHandler(tornado.web.RequestHandler):
        async def get(self) -> None:
            q = self.get_argument("q", "")
            wanted = [s for s in self.get_argument("sources", "").split(",") if s] or None
            custom = [u for u in self.get_argument("custom", "").split("|") if u.strip()]
            # scraping เป็น blocking I/O -> รันใน thread pool ไม่ให้ค้าง event loop
            loop = asyncio.get_running_loop()
            data = await loop.run_in_executor(None, run_search, q, wanted, custom)
            self.set_header("Content-Type", "application/json; charset=utf-8")
            self.write(json.dumps(data, ensure_ascii=False))

    installed = False
    for obj in gc.get_objects():
        if isinstance(obj, tornado.web.Application):
            obj.add_handlers(r".*", [(r"/api/search", SearchHandler)])
            installed = True
    return installed


@st.cache_data
def load_html(live: bool) -> str:
    html = HTML_FILE.read_text(encoding="utf-8")
    if live:
        # srcdoc iframe มี protocol เป็น about: -> เปิดทาง live backend ให้เอง
        html = html.replace(PROTOCOL_CHECK, "return true;", 1)
    return html


live_ready = install_search_api()

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
