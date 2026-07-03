#!/usr/bin/env python3
"""引用 DOI 活体核验(差异化功能,反 AI 编造参考文献)。

原理:从全文提取 DOI → 并发 HEAD https://doi.org/{doi}(不跟随跳转):
  301/302/303 = DOI 真实存在;404 = 疑似编造/抄错;超时/其他 = 未能核验。
零第三方依赖(urllib + 线程池),单次最多核验 MAX_DOIS 条。
返回与 analyze() 相同形状的 (level, title, findings)。
"""
from __future__ import annotations

import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

MAX_DOIS = 25
TIMEOUT = 6
_UA = "paper-check/1.0 (+https://paper-check-nt83.onrender.com)"

_DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\"'<>]+")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):  # noqa: D102
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def extract_dois(text: str) -> list[str]:
    """提取去重 DOI,保持出现顺序,去掉黏在结尾的标点。"""
    seen: dict[str, None] = {}
    for m in _DOI_RE.finditer(text):
        doi = m.group(0).rstrip(".,;:)]}。，；")
        seen.setdefault(doi, None)
    return list(seen)


def _probe(doi: str) -> tuple[str, str]:
    """返回 (doi, 'ok'|'missing'|'unknown')。"""
    req = urllib.request.Request(
        "https://doi.org/" + urllib.parse.quote(doi, safe="/()<>;:@&=+$,-_.!~*'"),
        method="HEAD", headers={"User-Agent": _UA},
    )
    try:
        _OPENER.open(req, timeout=TIMEOUT)
        return doi, "ok"          # 200(罕见,句柄直接应答)
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308):
            return doi, "ok"      # 跳转到出版商 = 存在
        if e.code == 404:
            return doi, "missing"
        return doi, "unknown"
    except Exception:
        return doi, "unknown"


def check_dois(raw: str) -> tuple:
    """核验全文 DOI。无 DOI → warn;有 404 → risk;全通过 → ok。"""
    dois = extract_dois(raw)
    title = "引用·DOI 活体核验"
    if not dois:
        return ("warn", title,
                ["- 未在文中发现 DOI,无法机器核验参考文献真伪(老文献/部分会议没有 DOI 属正常,但建议逐条人工确认——AI 生成的假引用是重灾区)"])

    capped = dois[:MAX_DOIS]
    with ThreadPoolExecutor(max_workers=10) as ex:
        probed = list(ex.map(_probe, capped))

    missing = [d for d, s in probed if s == "missing"]
    unknown = [d for d, s in probed if s == "unknown"]
    ok_n = sum(1 for _, s in probed if s == "ok")
    notes: list[str] = [f"- 共发现 {len(dois)} 个 DOI,核验 {len(capped)} 个:**{ok_n} 个真实存在**"]
    if missing:
        notes += [f"- 🚨 **DOI 无法解析(疑似编造或抄错):`{d}`** —— 去 doi.org 手动确认,别让审稿人先发现" for d in missing]
    if unknown:
        notes.append(f"- {len(unknown)} 个未能核验(网络超时/注册机构异常),建议手动复查:" + "、".join(f"`{d}`" for d in unknown[:5]))
    if len(dois) > MAX_DOIS:
        notes.append(f"- 超出单次核验上限,其余 {len(dois) - MAX_DOIS} 个未查")

    level = "risk" if missing else ("warn" if unknown else "ok")
    return (level, title, notes)
