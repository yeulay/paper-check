#!/usr/bin/env python3
"""投稿前自检 · 网页版(freemium micro-SaaS)。

商业模式:
  - 免费层:粘贴/上传论文 → 得到「体检总览」(各项 🟢🟡🔴 + 字数),制造价值感与钩子。
  - 付费层:输入解锁码 → 完整逐项报告(具体哪句超长、缺哪些声明…)+ 可下载。
    解锁码在环境变量 UNLOCK_CODE 配置;用户按页面收款方式付款后,你手动发码。
    这是零成本、当天可收钱的 MVP 做法;后续可换成 Stripe / 爱发电自动发货。

运行:
    pip install -r webapp/requirements.txt
    uvicorn webapp.main:app --reload --port 8000
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

# 复用 tools/ 里已验证的分析逻辑
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools.manuscript_check import analyze, read_docx, render_report, strip_latex  # noqa: E402
from webapp.venues import VENUES, check_venue  # noqa: E402

app = FastAPI(title="投稿前自检 · 网页版")

# 收款/解锁配置(用环境变量注入,别写死在代码里)
UNLOCK_CODE = os.environ.get("UNLOCK_CODE", "DEMO2026")
PAY_URL = os.environ.get("PAY_URL", "")          # 爱发电/收款码链接,页面展示
PRICE_TEXT = os.environ.get("PRICE_TEXT", "¥9.9 解锁完整报告")

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _extract_text(raw_bytes: bytes, filename: str) -> tuple[str, bool]:
    """返回 (text, is_tex)。.docx 走 python-docx,其余按文本解码。"""
    suffix = Path(filename).suffix.lower()
    if suffix == ".docx":
        tmp = Path("/tmp") / f"_upload_{os.getpid()}.docx"
        tmp.write_bytes(raw_bytes)
        try:
            return read_docx(tmp), False
        finally:
            tmp.unlink(missing_ok=True)
    return raw_bytes.decode("utf-8", errors="ignore"), suffix == ".tex"


def _summary(results: list[tuple]) -> list[dict]:
    """免费层:只给每项状态 + 标题(不含 findings 详情)。"""
    return [{"level": lv, "title": t} for lv, t, _ in results]


def _counts(results: list[tuple]) -> dict:
    risks = sum(1 for lv, _, _ in results if lv == "risk")
    warns = sum(1 for lv, _, _ in results if lv == "warn")
    oks = sum(1 for lv, _, _ in results if lv == "ok")
    return {"risk": risks, "warn": warns, "ok": oks}


@app.get("/api/venues")
async def venues() -> JSONResponse:
    return JSONResponse([{"key": k, "name": v["name"]} for k, v in VENUES.items()])


@app.post("/api/check")
async def check(text: str = Form(""), target_words: str = Form(""),
                unlock: str = Form(""), venue: str = Form("generic"),
                file: UploadFile | None = None):
    # 取文本:优先上传文件,否则用粘贴框
    if file is not None and file.filename:
        raw, is_tex = _extract_text(await file.read(), file.filename)
    else:
        raw, is_tex = (strip_latex(text) if False else text), False
    if not raw or not raw.strip():
        return JSONResponse({"error": "请粘贴论文文本或上传文件"}, status_code=400)

    tw = int(target_words) if target_words.strip().isdigit() else None
    results = analyze(raw, is_tex=is_tex, target_words=tw)
    plain = strip_latex(raw) if is_tex else raw
    results += check_venue(plain, raw, venue.strip() or "generic")

    paid = unlock.strip() == UNLOCK_CODE and UNLOCK_CODE != ""
    resp = {
        "counts": _counts(results),
        "summary": _summary(results),
        "paid": paid,
        "price_text": PRICE_TEXT,
        "pay_url": PAY_URL,
    }
    if paid:
        # 付费层:完整 findings + 现成 Markdown 报告
        resp["detail"] = [
            {"level": lv, "title": t, "findings": f} for lv, t, f in results
        ]
        resp["report_md"] = render_report("你的论文", results)
    else:
        # 免费层给一个"付费能看到什么"的诱饵:第一项风险项的 title
        first_risk = next((t for lv, t, _ in results if lv in ("risk", "warn")), None)
        resp["teaser"] = first_risk
    return resp


@app.get("/api/health")
async def health() -> PlainTextResponse:
    return PlainTextResponse("ok")


# 静态前端(落地页 + 工具),挂在根路径
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
