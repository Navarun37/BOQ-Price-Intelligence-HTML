"""BOQ Price Finder — Streamlit แสดงหน้า BOQ_price_finder.html เดิม + ดึงราคาสด

สถาปัตยกรรม (เวอร์ชัน stable page + transport component):
1) หน้า HTML เดิมฝังด้วย components.html ซึ่ง args คงที่ตลอด -> React ไม่มีวัน
   remount iframe หน้าจึงไม่ reload ระหว่างใช้งาน (custom component โดน
   remount ได้ระหว่าง rerun ซึ่งทำให้หน้าเด้ง/สถานะหาย)
2) มี "transport" custom component จิ๋วที่ซ่อนไว้ (สูง 0) ทำหน้าที่รับส่งข้อมูล:
   หน้าเว็บ ⇄ transport คุยกันผ่าน BroadcastChannel (same origin)
   transport ⇄ Python คุยผ่าน setComponentValue / render args ของ Streamlit
3) ตอน user กดค้นหา: หน้าเว็บ broadcast คำค้น -> transport ส่งเข้า Python ->
   run_search() ดึงราคาสดจาก server.py -> ส่งผลกลับทาง args -> broadcast กลับหน้าเว็บ

ทำไมไม่ใช้ HTTP endpoint (/api/search): edge proxy ของ Streamlit Cloud
ไม่ส่ง path ที่ไม่รู้จักมาถึงโปรเซสของแอป ช่องทาง component/websocket
เป็นกลไกหลักของ Streamlit จึงใช้ได้ทุกที่ที่แอป Streamlit รันได้

เวอร์ชัน UI แบบ Streamlit widgets เก็บไว้ที่ streamlit_app_widgets.py

รัน:  streamlit run streamlit_app.py
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from server import run_search

APP_DIR = Path(__file__).parent
HTML_FILE = APP_DIR / "BOQ_price_finder.html"
TRANSPORT_DIR = APP_DIR / ".boq_component"

# จุดที่ patch ในหน้า HTML (ตัวไฟล์ BOQ_price_finder.html เดิมไม่ถูกแก้)
PROTOCOL_CHECK = "return location.protocol === 'http:' || location.protocol === 'https:';"
FETCH_BLOCK = (
    "      const r = await fetch('/api/search?q='+encodeURIComponent(q)"
    "+'&sources='+sources+'&custom='+encodeURIComponent(custom));\n"
    "      if(!r.ok) throw new Error('HTTP '+r.status);\n"
    "      const d = await r.json();"
)
SEARCH_VIA_BRIDGE = "      const d = await window.__stSearch(q, sources, custom);"

PAGE_BRIDGE = """<script>
/* bridge ฝั่งหน้าเว็บ: ส่งคำค้นให้ transport component ผ่าน BroadcastChannel
   แล้วรอรับผลราคาสดกลับ (nonce จับคู่คำขอ-คำตอบ) */
(function(){
  const bc = new BroadcastChannel("boq-live-search");
  let pending = null, seq = 0;
  window.__stSearch = (q, sources, custom) => new Promise((resolve, reject) => {
    if(pending) pending.reject(new Error('superseded by a newer search'));
    const nonce = (++seq) + '-' + Date.now();
    pending = {nonce, resolve, reject};
    bc.postMessage({kind:"request", q:q, sources:sources, custom:custom, nonce:nonce});
    setTimeout(() => {
      if(pending && pending.nonce === nonce){
        const p = pending; pending = null;
        p.reject(new Error('live search timeout'));
      }
    }, 120000);
  });
  bc.onmessage = ev => {
    const m = ev.data || {};
    if(m.kind !== "response" || !pending || m.nonce !== pending.nonce) return;
    const p = pending; pending = null;
    if(m.payload && m.payload.__error) p.reject(new Error(m.payload.__error));
    else p.resolve(m.payload || {});
  };
})();
</script>
</body>"""

# transport component: หน้าเปล่าซ่อนไว้ ทำหน้าที่ต่อ BroadcastChannel เข้ากับ
# ช่อง setComponentValue/render ของ Streamlit เท่านั้น โดน remount ได้ไม่มีผล
TRANSPORT_HTML = """<!doctype html><html><head><meta charset="utf-8"></head><body><script>
(function(){
  const send = (type, data) => window.parent.postMessage(
    Object.assign({isStreamlitMessage:true, type:type}, data||{}), "*");
  const bc = new BroadcastChannel("boq-live-search");
  let delivered = null;
  bc.onmessage = ev => {
    const m = ev.data || {};
    if(m.kind !== "request") return;
    send("streamlit:setComponentValue", {dataType:"json",
      value:{q:m.q, sources:m.sources, custom:m.custom, nonce:m.nonce}});
  };
  window.addEventListener("message", ev => {
    const m = ev.data;
    if(!m || m.type !== "streamlit:render") return;
    const args = m.args || {};
    if(args.nonce && args.nonce !== delivered){
      delivered = args.nonce;
      bc.postMessage({kind:"response", nonce:args.nonce, payload:args.payload});
    }
  });
  send("streamlit:componentReady", {apiVersion: 1});
  send("streamlit:setFrameHeight", {height: 0});
})();
</script></body></html>"""


@st.cache_resource
def prepare_transport_dir() -> str:
    TRANSPORT_DIR.mkdir(exist_ok=True)
    (TRANSPORT_DIR / "index.html").write_text(TRANSPORT_HTML, encoding="utf-8")
    return str(TRANSPORT_DIR)


@st.cache_data
def load_page_html() -> str:
    html = HTML_FILE.read_text(encoding="utf-8")
    for target, repl in (
        (PROTOCOL_CHECK, "return true;"),   # srcdoc ไม่ใช่ http: -> เปิด live เสมอ
        (FETCH_BLOCK, SEARCH_VIA_BRIDGE),   # เปลี่ยน fetch เป็น bridge
        ("</body>", PAGE_BRIDGE),           # ติดตั้ง bridge ฝั่งหน้าเว็บ
    ):
        if html.count(target) != 1:
            raise RuntimeError("patch BOQ_price_finder.html ไม่ได้ (โครงไฟล์เปลี่ยน): %r" % target[:60])
        html = html.replace(target, repl, 1)
    return html


def handle_search(req: dict) -> dict:
    q = str(req.get("q") or "")
    wanted = [s for s in str(req.get("sources") or "").split(",") if s] or None
    custom = [u for u in str(req.get("custom") or "").split("|") if u.strip()]
    try:
        return run_search(q, wanted, custom)
    except Exception as e:  # ส่ง error กลับให้หน้าเว็บ fallback ไปโหมด offline
        return {"__error": str(e)}


st.set_page_config(
    page_title="BOQ Price Finder",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

_transport = components.declare_component("boq_transport", path=prepare_transport_dir())

# ซ่อน chrome ของ Streamlit / ซ่อน transport / ยืดหน้าเต็มจอ
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
      iframe[title="st.iframe"] {
        width: 100% !important;
        height: 100vh !important;
        border: none;
        display: block;
      }
      iframe[title*="boq_transport"] {
        height: 0 !important;
        min-height: 0 !important;
        border: none;
        display: block;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

components.html(load_page_html(), height=900, scrolling=True)

request = _transport(
    nonce=st.session_state.get("boq_nonce"),
    payload=st.session_state.pop("boq_payload", None),
    key="boq_transport",
    default=None,
)

# rerun ครั้งแรกของ session ทำให้ iframe โหลดใหม่ (พฤติกรรม frontend ของ Streamlit)
# จึง "จุด" rerun แรกทิ้งตั้งแต่ตอนโหลดหน้า ก่อน user จะทันกดค้นหา
if not st.session_state.get("_warmed_up"):
    st.session_state["_warmed_up"] = True
    st.rerun()

# มีคำค้นใหม่จากหน้าเว็บ -> ดึงราคาสดแล้ว rerun เพื่อส่งผลกลับทาง args
if request and request.get("nonce") and request["nonce"] != st.session_state.get("boq_nonce"):
    st.session_state["boq_payload"] = handle_search(request)
    st.session_state["boq_nonce"] = request["nonce"]
    st.rerun()
