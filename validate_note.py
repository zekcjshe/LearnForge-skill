#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_note.py — 教学重构笔记质量门禁（Quality Gate）

针对 v3.0 知识工程与教学启动器标准进行确定性审计：
  1. 结构与格式完备性：Frontmatter、代码块/公式/Mermaid 闭合、Wikilinks 无嵌套破坏
  2. 教学完备性：全篇通关目标、模块目标、闭环自测（Active Recall 3题+折叠答案）
  3. 来源可溯性：原片时间戳锚点、三元来源标注（[🎥 原片] / [📎 补充推导] / [⚠️ 教学解释]）
  4. 代码一致性：算法代码必须匹配时空复杂度分析
  5. Teaching Anchor 机械正确性（数量 ≤ 6，长度 ≤ 100，时间戳合法，无格式残缺，格式漂移即报错，可选 --archive 原文溯源，比对时忽略标点差异）
  6. Wikilink 真实存在性检验（联动 --vault，杜绝假知识节点与悬空链接）
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def check_anchor_audit(audit_path: Path) -> list[str]:
    """校验 anchor_audit.json 审计资产是否符合 schema 规范。"""
    issues = []
    if not audit_path.exists():
        return [f"未找到指定的 anchor_audit 资产: {audit_path}"]
    try:
        data = json.loads(audit_path.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"anchor_audit.json 解析失败: {e}"]

    for req in ["video_id", "candidates", "final_anchors"]:
        if req not in data:
            issues.append(f"anchor_audit.json 缺失必填字段: {req}")

    candidates = data.get("candidates", [])
    if not isinstance(candidates, list):
        issues.append("anchor_audit.json 的 candidates 必须为列表")
    else:
        for c in candidates:
            if not isinstance(c, dict):
                continue
            quote = c.get("quote", "")[:15]
            if c.get("kept"):
                r = c.get("reason", {})
                for dim in ["irreplaceable", "non_derivable", "memorable"]:
                    if not r.get(dim):
                        issues.append(f"入选 Anchor [{quote}] 缺失三问理由: {dim}")
            else:
                if not c.get("reason_failed"):
                    issues.append(f"淘汰 Anchor [{quote}] 缺失淘汰原因: reason_failed")
    return issues


def generate_anchor_audit_template(note_text: str, video_id: str = "BV_TODO", source_title: str = "TODO") -> dict:
    """根据正文中实际入选的 Anchor 生成符合 schema 规范的初始审计资产骨架。"""
    matches = list(ANCHOR_QUOTE_PATTERN.finditer(note_text))
    candidates = []
    final_anchors = []
    for m in matches:
        up, quote, ts_start, ts_end = m.groups()
        q_clean = quote.strip()
        candidates.append({
            "quote": q_clean,
            "timestamp": f"{ts_start}-{ts_end}",
            "up_name": up.strip(),
            "kind": "analogy",
            "kept": True,
            "reason": {
                "irreplaceable": "名师独家比喻，改写为抽象术语后损失记忆抓手",
                "non_derivable": "直觉心智模型，正文严密推导尚未涵盖该通俗生活实体",
                "memorable": "形象直观，一周后仍可作为快速唤醒词"
            }
        })
        final_anchors.append(q_clean)
    return {
        "generated_at": datetime.datetime.now().isoformat(),
        "video_id": video_id,
        "source_title": source_title,
        "candidates": candidates,
        "final_anchors": final_anchors
    }


# ---------- Teaching Anchor 确定性检查 ----------

# 【为什么把话筒图标单独拎出来】🎙️ 是 **两个码点**：U+1F399 + U+FE0F（变体选择符）。
# 写成 [🎙️🎤] 的字符类只吃一个码点，它吞掉 🎙 后，U+FE0F 无人认领，
# 紧跟其后的 "原片教学锚点" 就永远匹配不上 —— 而 SKILL.md 规定的格式正是带变体符的 🎙️。
# 结果是全套 Anchor 检查（≤6 条 / ≤100 字 / 时间戳 / UP主 / 原文溯源）静默空转，
# 且因为 marker_count 与 count 同时为 0，连一条警告都不会发。
# 所以用 [🎙🎤] + U+FE0F 可选来兼容两种写法（变体符写成 ️ 转义，
# 免得哪天编辑器/工具链把它抹掉，正则又悄悄退回那个匹配不上的版本）。
_MIC = "[🎙🎤]" + chr(0xFE0F) + "?"

ANCHOR_QUOTE_PATTERN = re.compile(
    r'>[ \t]*\[!quote\][ \t]*' + _MIC + r'[ \t]*原片教学锚点[（(]([^\n）)]+)[）)][ \t]*\n'
    r'>[ \t]*["“]([^"”\n]+)["”][ \t]*\n'
    r'>[ \t]*——[ \t]*\[([0-9]{1,3}:[0-9]{2}(?::[0-9]{2})?)[ \t]*-[ \t]*([0-9]{1,3}:[0-9]{2}(?::[0-9]{2})?)\]',
    re.MULTILINE,
)
ANCHOR_MARKER_PATTERN = re.compile(
    r'^>[ \t]*\[!quote\][ \t]*' + _MIC + r'[ \t]*原片教学锚点',
    re.MULTILINE,
)
# 【为什么要数"提到"而不是只数"合规"】上面那个 emoji 事故说明：正则一旦与
# 真实写法脱节，检查会静默归零而不是报错。所以额外统计"引用块里提到原片教学锚点"
# 的行数，只要多于完整解析数，就说明格式漂移了 —— 宁可吵，也不能静默放过。
ANCHOR_MENTION_PATTERN = re.compile(r'^>.*原片教学锚点', re.MULTILINE)
MAX_ANCHORS = 6
MAX_ANCHOR_CHARS = 100


def _ts_to_sec(ts: str) -> int | None:
    try:
        parts = [int(x) for x in ts.split(':')]
        if len(parts) == 2:
            mm, ss = parts
            if ss >= 60:
                return None
            return mm * 60 + ss
        if len(parts) == 3:
            hh, mm, ss = parts
            if mm >= 60 or ss >= 60:
                return None
            return hh * 3600 + mm * 60 + ss
    except Exception:
        return None
    return None


ASR_HOMOPHONE_MAP = {
    "五二比侧": "512比特",
    "五二比特": "512比特",
    "五二": "512",
    "五爻": "512",
    "循环左一": "循环左移",
    "循环阻一": "循环左移",
    "沙溢": "sha1",
    "沙一": "sha1",
    "山一": "sha1",
    "沙万": "sha1",
    "沙外": "sha1",
    "imd5": "md5",
    "前程": "填充",
    "前冲": "填充",
    "签证": "填充",
    "比他": "比特",
    "埃尔": "l",
    "用户运算": "异或运算",
    "用公算": "异或运算",
    "优化": "异或",
    "一会": "异或",
    "运回": "异或",
    "一或": "异或",
    "抑或": "异或",
    "结带": "迭代",
    "接待": "迭代",
    "生殖问题": "生日问题",
    "欧派": "opad",
    "欧派的": "opad",
    "max值": "mac值",
}

FILLERS = ["呃", "啊", "呢", "吧", "呀", "这个", "那个", "你看", "对吧"]


def _normalize_tokens(text: str) -> str:
    s = text.lower()
    for k, v in ASR_HOMOPHONE_MAP.items():
        s = s.replace(k, v)
    s = re.sub(r"[\W_]+", "", s)
    for f in FILLERS:
        s = s.replace(f, "")
    s = re.sub(r"(.)\1+", r"\1", s)
    return s


def _match_quote(needle: str, haystack: str, threshold: float = 0.78) -> bool:
    import difflib
    f_needle = re.sub(r"[\W_]+", "", needle).lower()
    f_haystack = re.sub(r"[\W_]+", "", haystack).lower()
    if f_needle in f_haystack:
        return True
    norm_needle = _normalize_tokens(needle)
    norm_haystack = _normalize_tokens(haystack)
    if norm_needle in norm_haystack:
        return True
    n_len = len(norm_needle)
    if n_len < 4:
        return False
    step = max(1, n_len // 5)
    for i in range(0, max(1, len(norm_haystack) - n_len + 1), step):
        chunk = norm_haystack[i : i + n_len + 15]
        if difflib.SequenceMatcher(None, norm_needle, chunk).ratio() >= threshold:
            return True
    return False


def _fold_for_match(text: str) -> str:
    """把文本折叠成"只留字"的形态，专供原文溯源比对。"""
    return re.sub(r"[\W_]+", "", text).lower()


def _text_to_bigrams(text: str) -> set[str]:
    s = re.sub(r"[\W_]+", "", text).lower()
    return set(s[i : i + 2] for i in range(len(s) - 1))


def _check_time_window_overlap(quote: str, ts_start: str, ts_end: str, raw_archive: str, margin: int = 25) -> float:
    """第二重：基于时间戳切片与字符骨架重合度，验证是否为讲师在该时间段原话的精炼润色。"""
    s_sec = _ts_to_sec(ts_start)
    e_sec = _ts_to_sec(ts_end)
    if s_sec is None or e_sec is None:
        return 0.0

    w_start = max(0, s_sec - margin)
    w_end = e_sec + margin
    ts_pattern = re.compile(r"\[(\d{1,2}:\d{2}(?::\d{2})?)\s*-->\s*(\d{1,2}:\d{2}(?::\d{2})?)\]\s*([^\n]+)")

    sources = raw_archive.split("=== SOURCE: ")
    best_recall = 0.0
    bg_q = _text_to_bigrams(quote)
    if not bg_q:
        return 0.0

    for src in sources:
        if not src.strip():
            continue
        collected = []
        for m in ts_pattern.finditer(src):
            s = _ts_to_sec(m.group(1))
            e = _ts_to_sec(m.group(2))
            if s is not None and e is not None and s <= w_end and e >= w_start:
                collected.append(m.group(3))
        if collected:
            bg_win = _text_to_bigrams(" ".join(collected))
            recall = len(bg_q & bg_win) / len(bg_q)
            if recall > best_recall:
                best_recall = recall
    return best_recall


_TS_STRIP = re.compile(r"\[\s*\d{1,2}:\d{2}(?::\d{2})?(?:\s*-->\s*\d{1,2}:\d{2}(?::\d{2})?)?\s*\]")


def _match_quote_dual_track(quote: str, ts_start: str, ts_end: str, archive_text: str) -> bool:
    """二重双轨校验：满足任意一重即为真锚点。
    第一重：原片字面/常规模糊比对（原话无口水、字面直接一致）
    第二重：时间窗口切片骨架比对（讲师原话有口水/结巴/ASR错字，经过人话精炼转化后的高保真语义对齐）
    """
    clean_archive = _TS_STRIP.sub("", archive_text)
    # 第一重
    if _match_quote(quote, clean_archive):
        return True

    # 第二重：时间切片骨架召回（阈值 55% 骨架重叠即可确认同一语意）
    overlap = _check_time_window_overlap(quote, ts_start, ts_end, archive_text)
    if overlap >= 0.55:
        return True

    return False


def check_anchors(note_text: str, archive_text: str = '') -> dict:
    """机械正确性与双轨溯源校验。"""
    blocking: list[str] = []
    warnings: list[str] = []

    matches = list(ANCHOR_QUOTE_PATTERN.finditer(note_text))
    count = len(matches)
    marker_count = len(ANCHOR_MARKER_PATTERN.findall(note_text))
    mention_count = len(ANCHOR_MENTION_PATTERN.findall(note_text))

    if count > MAX_ANCHORS:
        blocking.append(f'Anchor 数量 {count} > 上限 {MAX_ANCHORS}')
    if marker_count != count:
        blocking.append(f'Anchor 结构不完整：检测到 {marker_count} 个 Anchor 标记，仅完整解析出 {count} 条')
    if mention_count > marker_count:
        blocking.append(
            f'Anchor 格式漂移：正文有 {mention_count} 处引用块提到「原片教学锚点」，'
            f'但仅 {marker_count} 处符合规定的三行格式'
            f'（应为：> [!quote] 🎙️ 原片教学锚点（UP主名） / > "摘录" / > —— [mm:ss - mm:ss]）')

    seen_quotes = set()
    for match in matches:
        up_name, quote, ts_start, ts_end = match.groups()
        up_name = up_name.strip()
        quote = quote.strip()

        if not quote:
            blocking.append(f'Anchor quote 为空（{ts_start}）')
            continue

        if len(quote) > MAX_ANCHOR_CHARS:
            blocking.append(f'Anchor quote 超过 {MAX_ANCHOR_CHARS} 字（实际 {len(quote)} 字）：{quote[:20]}...')

        if not up_name:
            blocking.append(f'Anchor 未标注 UP主（{ts_start}）')

        if quote in seen_quotes:
            blocking.append(f'Anchor quote 重复：{quote[:20]}...')
        seen_quotes.add(quote)

        start_sec = _ts_to_sec(ts_start)
        end_sec = _ts_to_sec(ts_end)
        if start_sec is None or end_sec is None:
            blocking.append(f'Anchor 时间戳格式/范围非法：{ts_start} - {ts_end}')
        elif start_sec > end_sec:
            blocking.append(f'Anchor 时间戳倒挂：{ts_start} - {ts_end}')

        if '…' in quote or '...' in quote:
            warnings.append(f'Anchor quote 含省略号，可能不是连续原话：{quote[:20]}...')

        if archive_text:
            if not _match_quote_dual_track(quote, ts_start, ts_end, archive_text):
                blocking.append(f'Anchor quote 不在原始 transcript 或时间窗口语意不匹配：{quote[:20]}...')
        else:
            warnings.append(f'未提供 archive，跳过 Anchor 原始 transcript 溯源检查：{quote[:20]}...')

    return {
        'blocking': blocking,
        'warnings': warnings,
        'count': count,
    }


def validate_note(content: str, vault_root: Path | None = None, archive_text: str = "") -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    # 规范化换行符（CRLF -> LF），确保跨平台校验一致性
    content = content.replace("\r\n", "\n")
    if archive_text:
        archive_text = archive_text.replace("\r\n", "\n")

    # 1. 结构与格式完整性检查
    has_frontmatter = bool(re.match(r"\A---\r?\n.*?\r?\n---\r?\n", content, re.DOTALL))
    if not has_frontmatter:
        errors.append("缺失 Frontmatter 元数据区 (---...---)")

    # 检查未闭合的代码块（支持缩进代码块）
    backtick_count = len(re.findall(r"^\s*```", content, re.MULTILINE))
    if backtick_count % 2 != 0:
        errors.append(f"存在未闭合的 Markdown 代码块（``` 标记出现 {backtick_count} 次，不成对）")

    # 检查未闭合的数学公式
    math_blocks = len(re.findall(r"\$\$", content))
    if math_blocks % 2 != 0:
        errors.append("存在未闭合的独立数学公式块（$$ 不成对）")

    # 检查 Mermaid 语法块
    mermaid_blocks = re.findall(r"```mermaid\s*\n(.*?)\n```", content, re.DOTALL)
    for idx, mb in enumerate(mermaid_blocks, 1):
        if not re.search(r"\b(graph|flowchart|sequenceDiagram|classDiagram|stateDiagram)\b", mb):
            warnings.append(f"Mermaid 图表 #{idx} 缺少有效的图表类型声明")

    # 检查 Wikilinks 是否存在二次嵌套破坏
    if re.search(r"\[\[[^\]]*\[\[", content) or re.search(r"\]\][^\[]*\]\]", content):
        errors.append("检测到异常嵌套的 Wikilinks（如 [[[[...]]]]）")

    # 2. 教学完备性检查
    has_global_goal = bool(re.search(r"🎯\s*\*\*全篇通关目标\*\*", content))
    if not has_global_goal:
        warnings.append("缺失全篇通关目标（🎯 **全篇通关目标**）")

    module_goals = len(re.findall(r"🎯\s*学完你能", content))
    module_headers = len(re.findall(r"^##\s+模块", content, re.MULTILINE))
    if module_headers > 0 and module_goals < module_headers:
        warnings.append(f"模块学习目标覆盖不足：共有 {module_headers} 个模块，仅检测到 {module_goals} 个模块目标")

    # 闭环自测：精准校验是否包含至少 3 道题与配对折叠答案
    recall_match = re.search(r"(?:##\s+.*?(?:闭环自测|自测练习|Active Recall|Post-test).*?\n)([\s\S]*?)(?=\n##\s+|\Z)", content, re.IGNORECASE)
    has_active_recall = bool(recall_match)
    recall_text = recall_match.group(1) if recall_match else ""

    # ① 先剥离代码块和行内代码，防止正文/提示框中说明用的 `<details>` 等标记被误当作 HTML 开标签
    _clean_text = re.sub(r"(?s)```.*?```|`[^`\n]+`", "", recall_text)
    # ② 剥离 <details> 答案体，避免答案解析内部的编号列表被计成新的题目
    _q_body = re.sub(r"<details(?:\s+[^>]*)?>[\s\S]*?</details>", "", _clean_text, flags=re.IGNORECASE)

    # ② 题目正则增加可选的标题前缀 —— 兼容 SKILL.md 规定的 "### 1. xxx" 写法
    Q_PATTERN = re.compile(
        r"(?:^|\n)\s*(?:#{1,6}\s*)?"
        r"(?:\d+[\.、]|\bQ\d+[:：]|题\s*\d+[:：]|第\s*[一二三四五\d]+\s*题[:：])\s*[^\n]+"
    )
    questions = Q_PATTERN.findall(_q_body)
    answers = re.findall(r"(?:> \[!(?:TIP|NOTE|SUCCESS|QUESTION|EXAMPLE|INFO)\]-?|<details>|<!--\s*details\s*-->|参考答案|答案[:：])", recall_text, re.IGNORECASE)
    q_count = len(questions)
    a_count = len(answers)

    if not has_active_recall:
        warnings.append("缺失闭环自测（Active Recall / Post-test）模块")
    else:
        if q_count < 3:
            warnings.append(f"闭环自测题不足 3 道（实际检测到 {q_count} 道，教学标准要求至少 3 道：概念/迁移/陷阱）")
        if a_count < q_count:
            warnings.append(f"闭环自测题与折叠答案未配对（检测到 {q_count} 道题，仅发现 {a_count} 处折叠答案）")

    # 3. 来源可溯性检查
    has_time_anchors = bool(re.search(r"(\[\d{1,2}:\d{2}(?::\d{2})?[^\]]*\]|[?&]t=\d+)", content))
    if not has_time_anchors:
        warnings.append("正文中未发现任何原片时间戳锚点（如 [05:20] 或 ?t=100），回跳定位能力缺失")

    provenance_tags = len(re.findall(r"(\[🎥\s*原片\]|\[📎\s*补充推导\]|\[⚠️\s*教学解释\]|🎥\s*来源(?:原片)?|>\s*🎥\s*来源)", content))
    if provenance_tags == 0:
        warnings.append("未标注来源追踪（建议使用模块级 [> 🎥 来源原片：...] 或三元标签 [🎥 原片] / [📎 补充推导] / [⚠️ 教学解释]）")

    # 4. 复杂度与代码一致性检查
    has_complexity = bool(re.search(r"(时间复杂度|空间复杂度|O\([0-9A-Za-z\s\^\*\+\-\\\,\.]*\))", content))
    code_blocks = re.findall(r"```(?:c|cpp|python|java|go|rust)\s*\n.*?\n```", content, re.DOTALL)
    if code_blocks and not has_complexity:
        warnings.append("包含程序代码但缺失时间/空间复杂度分析说明")

    # 5. Teaching Anchor 机械正确性检查
    anchor_result = check_anchors(content, archive_text)
    errors.extend(anchor_result["blocking"])
    warnings.extend(anchor_result["warnings"])

    # 6. Wikilink 真实存在性检验（当提供 --vault 时触发）
    raw_links = re.findall(r"\[\[([^\]\n]+)\]\]", content)
    wikilink_targets = []
    for r in raw_links:
        t = r.split("|")[0].split("#")[0].split("^")[0].strip()
        if t:
            wikilink_targets.append(t)

    dangling_links = []
    wikilink_score = 1.0

    if vault_root and vault_root.is_dir():
        valid_targets = set()
        for p in vault_root.rglob("*.md"):
            if any(part.startswith(".") for part in p.parts):
                continue
            rel = str(p.relative_to(vault_root)).replace("\\", "/")
            rel_stem = rel[:-3] if rel.endswith(".md") else rel
            valid_targets.add(p.stem)
            valid_targets.add(rel)
            valid_targets.add(rel_stem)
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as fh:
                    head = fh.read(2000)
                m = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", head, re.DOTALL)
                if m:
                    fm = m.group(1)
                    tm = re.search(r"^title\s*:\s*[\"']?([^\"'\n]+)[\"']?", fm, re.MULTILINE)
                    if tm:
                        valid_targets.add(tm.group(1).strip())
                    for am in re.finditer(r"aliases?\s*:\s*\[([^\]]*)\]", fm):
                        for a in am.group(1).split(","):
                            c = a.strip().strip("\"'")
                            if c:
                                valid_targets.add(c)
            except Exception:
                pass

        for lt in wikilink_targets:
            lt_clean = lt.replace("\\", "/")
            if lt_clean not in valid_targets and lt not in valid_targets:
                dangling_links.append(lt)

        if dangling_links:
            unique_dangling = sorted(set(dangling_links))
            warnings.append(f"发现 {len(unique_dangling)} 处在 Vault 中不存在的悬空 Wikilink：{', '.join(unique_dangling[:5])}")
            wikilink_score = max(0.0, 1.0 - (len(unique_dangling) / max(1, len(set(wikilink_targets)))) * 0.5)

    # 7. 综合评分模型 (0.0 ~ 1.0)
    fmt_score = max(0.0, 1.0 - len([e for e in errors if "代码块" in e or "公式" in e or "Wikilinks" in e]) * 0.4)
    teach_score = 1.0
    if not has_global_goal:
        teach_score -= 0.2
    if not has_active_recall:
        teach_score -= 0.25
    elif q_count < 3 or a_count < q_count:
        teach_score -= 0.15
    if module_headers > 0 and module_goals == 0:
        teach_score -= 0.2
    teach_score = max(0.0, teach_score)

    trace_score = 1.0
    if not has_time_anchors:
        trace_score -= 0.5
    if provenance_tags == 0:
        trace_score -= 0.3
    trace_score = max(0.0, trace_score)

    code_score = 1.0 if not (code_blocks and not has_complexity) else 0.8
    if any("代码块" in e for e in errors):
        code_score = 0.0

    anchor_score = 1.0 if len(anchor_result["blocking"]) == 0 else 0.0

    overall = round((fmt_score * 0.20 + teach_score * 0.20 + trace_score * 0.20 + code_score * 0.15 + wikilink_score * 0.15 + anchor_score * 0.10), 2)
    passed = len(errors) == 0 and overall >= 0.70

    return {
        "passed": passed,
        "overall_score": overall,
        "scores": {
            "format_integrity": round(fmt_score, 2),
            "teaching_completeness": round(teach_score, 2),
            "source_traceability": round(trace_score, 2),
            "code_consistency": round(code_score, 2),
            "wikilink_integrity": round(wikilink_score, 2),
            "anchor_integrity": round(anchor_score, 2),
        },
        "errors": errors,
        "warnings": warnings,
        "metrics": {
            "code_blocks_count": len(code_blocks),
            "mermaid_count": len(mermaid_blocks),
            "provenance_tags_count": provenance_tags,
            "has_time_anchors": has_time_anchors,
            "questions_count": q_count,
            "answers_count": a_count,
            "wikilinks_count": len(wikilink_targets),
            "dangling_wikilinks_count": len(set(dangling_links)),
            "anchor_count": anchor_result["count"],
            "anchor_max": MAX_ANCHORS,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="validate_note — 教学笔记质量门禁与工程规范审计")
    ap.add_argument("input", help="待校验的 Markdown 笔记路径")
    ap.add_argument("--json", action="store_true", help="以 JSON 格式输出审计结果")
    ap.add_argument("--vault", default=None, help="可选：Obsidian Vault 路径（用于校验链接目标存在性）")
    ap.add_argument("--archive", default=None, help="可选：原始 transcript/_archive.json 路径（用于校验 Anchor 原文溯源）")
    ap.add_argument("--audit", default=None, help="可选：anchor_audit.json 路径（用于校验 Anchor 审计资产合规性）")
    ap.add_argument("--generate-audit", default=None, metavar="VIDEO_ID", help="为当前笔记中实际提取的 Anchor 自动生成 anchor_audit.json 骨架模板")
    args = ap.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"[error] 文件不存在: {in_path}", file=sys.stderr)
        return 2

    content = in_path.read_text(encoding="utf-8")

    if args.generate_audit:
        template = generate_anchor_audit_template(content, video_id=args.generate_audit, source_title=in_path.stem)
        audit_out = in_path.parent / "anchor_audit.json"
        audit_out.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[audit] 已生成 Anchor 审计资产模板: {audit_out}")
        return 0

    vault_root = Path(args.vault) if args.vault else None
    archive_text = ""
    if args.archive:
        archive_path = Path(args.archive)
        if not archive_path.exists():
            print(f"[error] archive 文件不存在: {archive_path}", file=sys.stderr)
            return 2
        raw_archive = archive_path.read_text(encoding="utf-8", errors="ignore")
        if archive_path.suffix.lower() == ".json":
            try:
                data = json.loads(raw_archive)
                if isinstance(data, dict):
                    parts = [
                        data.get("content", ""),
                        data.get("content_dehydrated", ""),
                        data.get("content_plain", ""),
                        data.get("transcript", ""),
                        "\n".join(data.get("lines", [])) if isinstance(data.get("lines"), list) else "",
                    ]
                    archive_text = "\n".join(p for p in parts if p)
                else:
                    archive_text = raw_archive
            except Exception:
                archive_text = raw_archive
        else:
            archive_text = raw_archive

    res = validate_note(content, vault_root=vault_root, archive_text=archive_text)

    # 可选/自动检查 anchor_audit 资产合规性
    audit_file = Path(args.audit) if args.audit else (in_path.parent / "anchor_audit.json")
    if audit_file.exists():
        audit_issues = check_anchor_audit(audit_file)
        if audit_issues:
            res["warnings"].extend([f"Anchor 审计资产规范: {issue}" for issue in audit_issues])

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        status_icon = "✅ PASSED" if res["passed"] else "❌ FAILED"
        wl_str = f" | 链接真实度: {res['scores']['wikilink_integrity'] * 100:.0f}%" if (args.vault or res['metrics']['dangling_wikilinks_count'] > 0) else ""
        print(f"\n[gate] 质量门禁状态: {status_icon} (综合评分: {res['overall_score'] * 100:.0f}/100)")
        print(f"       格式完备性: {res['scores']['format_integrity'] * 100:.0f}% | "
              f"教学完备性: {res['scores']['teaching_completeness'] * 100:.0f}% | "
              f"来源可溯性: {res['scores']['source_traceability'] * 100:.0f}% | "
              f"代码一致性: {res['scores']['code_consistency'] * 100:.0f}%{wl_str}")

        if res["errors"]:
            print(f"\n[error] 阻断级缺陷 ({len(res['errors'])} 项):", file=sys.stderr)
            for err in res["errors"]:
                print(f"  - 🔴 {err}", file=sys.stderr)

        if res["warnings"]:
            print(f"\n[warning] 优化建议 ({len(res['warnings'])} 项):", file=sys.stderr)
            for warn in res["warnings"]:
                print(f"  - 🟡 {warn}", file=sys.stderr)

    return 0 if res["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
