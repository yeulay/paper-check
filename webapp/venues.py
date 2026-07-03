#!/usr/bin/env python3
"""目标期刊/会议定向检查(差异化功能)。

每个预设定义:摘要词数上限、是否双盲、必备段落标记、参考文献风格。
check_venue() 返回与 tools.manuscript_check.analyze() 相同形状的
[(level, title, findings), ...],直接追加到通用检查结果后面。
"""
from __future__ import annotations

import re

# marker: (正则, 人类可读名)
VENUES: dict[str, dict] = {
    "generic": {
        "name": "通用 SCI/EI(默认)",
    },
    "ieee_trans": {
        "name": "IEEE Transactions 期刊",
        "abstract_max": 250,
        "ref_style": "numeric",
        "markers": [
            (r"(?i)\bindex\s+terms\b", "Index Terms(IEEE 关键词段)"),
        ],
        "tips": [
            "用 IEEEtran 模板(双栏);图表引用写作 Fig. 1 / Table I",
            "参考文献按出现顺序编号 [1],期刊名用 IEEE 标准缩写",
        ],
    },
    "acm": {
        "name": "ACM 会议/期刊",
        "abstract_max": 250,
        "ref_style": "numeric",
        "markers": [
            (r"(?i)\bccs\s+concepts\b", "CCS Concepts(ACM 分类段)"),
            (r"(?i)\bkeywords\b", "Keywords 段"),
        ],
        "tips": [
            "用 acmart 模板;CCS Concepts 在 dl.acm.org/ccs 生成",
        ],
    },
    "neurips_icml": {
        "name": "NeurIPS / ICML / ICLR",
        "double_blind": True,
        "markers": [],
        "tips": [
            "正文页数限制严格(NeurIPS 9 页,ICML 8 页,不含参考文献/附录)",
            "投稿版须匿名;NeurIPS 需在附录填 paper checklist",
            "Broader impact / limitations 段建议保留",
        ],
    },
    "cvpr_iccv": {
        "name": "CVPR / ICCV / ECCV",
        "double_blind": True,
        "markers": [],
        "tips": [
            "8 页双栏(不含参考文献);超页会被 desk reject",
            "投稿版匿名;补充材料单独打包,正文不可依赖补充材料成立",
        ],
    },
    "aaai_ijcai": {
        "name": "AAAI / IJCAI",
        "double_blind": True,
        "markers": [],
        "tips": [
            "AAAI 7+2 页(参考文献 2 页);IJCAI 7+2,超页需付费",
            "投稿版匿名;AAAI 需提交 reproducibility checklist",
        ],
    },
    "elsevier": {
        "name": "Elsevier 期刊",
        "abstract_max": 300,
        "markers": [
            (r"(?i)\bhighlights\b", "Highlights(3–5 条,每条 ≤85 字符)"),
            (r"(?i)\bcredit\s+author(ship)?\s+(statement|contribution)|author\s+contributions?\b",
             "CRediT author statement(作者贡献声明)"),
            (r"(?i)declaration\s+of\s+(competing|conflicting)\s+interests?|conflicts?\s+of\s+interest",
             "Declaration of competing interest"),
        ],
        "tips": [
            "多数刊要求 Highlights 单独文件;投稿系统里逐条粘贴",
        ],
    },
    "springer": {
        "name": "Springer 期刊",
        "abstract_max": 250,
        "markers": [
            (r"(?i)\bdeclarations?\b|\bfunding\b", "Declarations 段(funding/COI/ethics 合并)"),
        ],
        "tips": [
            "Springer 统一要求文末 Declarations 段;部分刊要求结构化摘要",
        ],
    },
}

_ANON_LEAKS = [
    (r"(?i)\bour\s+(previous|prior|earlier)\s+work\b", "自引措辞暴露身份(our previous work → the work of [X])"),
    (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "正文含邮箱地址"),
    (r"(?i)^\s*acknowledg(e)?ments?\b", "含致谢段(投稿版应删除)"),
]


def _extract_abstract(plain: str) -> str | None:
    m = re.search(
        r"(?is)\babstract\b[:.\s]*\n?(.{40,4000}?)(?=\n\s*(?:1[\s.]|I\.|introduction\b|keywords\b|index\s+terms\b|ccs\s+concepts\b))",
        plain,
    )
    return m.group(1).strip() if m else None


def check_venue(plain: str, raw: str, venue_key: str) -> list[tuple]:
    """针对目标 venue 的附加检查,形状同 analyze() 的结果项。"""
    v = VENUES.get(venue_key)
    if not v or venue_key == "generic":
        return []
    results: list[tuple] = []
    vname = v["name"]

    # 1) 摘要长度
    if v.get("abstract_max"):
        abstract = _extract_abstract(plain)
        title = f"定向·摘要长度({vname} ≤{v['abstract_max']} 词)"
        if abstract is None:
            results.append(("warn", title, ["- 未识别出 Abstract 段,无法核对长度(确认有以 Abstract 开头的摘要)"]))
        else:
            n = len(abstract.split())
            if n > v["abstract_max"]:
                results.append(("risk", title, [f"- 摘要约 **{n} 词**,超出上限 {v['abstract_max']} 词,超长是常见退稿理由"]))
            else:
                results.append(("ok", title, [f"- 摘要约 {n} 词,在上限内"]))

    # 2) 双盲匿名
    if v.get("double_blind"):
        leaks = []
        for pat, desc in _ANON_LEAKS:
            hits = re.findall(pat, plain, flags=re.M)
            if hits:
                leaks.append(f"- {desc}(命中 {len(hits)} 处)")
        title = f"定向·双盲匿名({vname})"
        if leaks:
            results.append(("risk", title, leaks))
        else:
            results.append(("ok", title, ["- 未发现明显身份泄露(仍建议人工复查作者信息/资助号)"]))

    # 3) 必备段落
    missing = [name for pat, name in v.get("markers", []) if not re.search(pat, plain)]
    if v.get("markers"):
        title = f"定向·必备段落({vname})"
        if missing:
            results.append(("warn", title, [f"- 缺少:**{m}**" for m in missing]))
        else:
            results.append(("ok", title, ["- 该目标要求的专有段落都在"]))

    # 4) 参考文献编号风格
    if v.get("ref_style") == "numeric":
        numeric = len(re.findall(r"\[\d+([,–-]\s*\d+)*\]", raw))
        author_year = len(re.findall(r"\([A-Z][A-Za-z-]+(?:\s+(?:et\s+al\.?|and|&)\s+[A-Za-z-]+)?,?\s+(19|20)\d{2}[a-z]?\)", raw))
        title = f"定向·引用风格({vname} 要求数字编号)"
        if author_year > numeric and author_year >= 3:
            results.append(("warn", title,
                            [f"- 检测到 **{author_year}** 处作者-年份式引用、{numeric} 处数字式,目标要求 [1] 数字编号,注意转换"]))
        else:
            results.append(("ok", title, [f"- 数字式引用 {numeric} 处,符合要求"]))

    # 5) 人工核对清单(机器查不了但必看)
    if v.get("tips"):
        results.append(("warn", f"定向·投稿须知清单({vname})", [f"- {t}" for t in v["tips"]]))
    return results
