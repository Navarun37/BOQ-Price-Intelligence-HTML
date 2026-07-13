"""Live search API สำหรับเวอร์ชัน Streamlit

เพิ่ม endpoint /api/search เข้าไปใน Tornado server ที่ Streamlit รันอยู่แล้ว
(tornado เป็น dependency บังคับของ streamlit จึงมีเสมอ) โดย handler
เรียก run_search() จาก server.py เพื่อดึงราคาสดจากเว็บร้านตอน user ค้นหา

แยกออกมาจาก streamlit_app.py เพื่อให้ wrapper หลักเรียบง่าย
และ import แบบ optional ได้ — ถ้าโมดูลนี้ใช้ไม่ได้ หน้าเว็บยังทำงานโหมด offline
"""
from __future__ import annotations

import asyncio
import gc
import json

import tornado.routing
import tornado.web

from server import run_search


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


def install_search_api() -> bool:
    """จดทะเบียน /api/search เข้า Tornado app ของ Streamlit (เรียกซ้ำได้ปลอดภัย)"""
    installed = False
    for obj in gc.get_objects():
        if isinstance(obj, tornado.web.Application):
            rules = getattr(getattr(obj, "wildcard_router", None), "rules", None)
            if rules is not None:
                exists = any(
                    getattr(getattr(rule, "matcher", None), "_path", "") == r"/api/search"
                    for rule in rules
                )
                if not exists:
                    # Streamlit มี catch-all route สำหรับ frontend อยู่ท้าย/กลาง list
                    # จึงต้อง prepend ไม่ใช่ add_handlers() ที่ append แล้วโดน catch-all กลบ
                    rules.insert(0, tornado.routing.Rule(
                        tornado.routing.PathMatches(r"/api/search"),
                        SearchHandler,
                    ))
                installed = True
                continue
            obj.add_handlers(r".*", [(r"/api/search", SearchHandler)])
            installed = True
    return installed
