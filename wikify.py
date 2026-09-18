#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wikify.py — Vault 索引与 Wikilinks 幂等注入引擎

子命令：
  scan    扫描 Obsidian Vault，建索引（缓存到 ~/.cache/video2obsidian/vault_index.json）
  inject  读 raw.md + terms.json，注入 [[...]]，输出 final.md + audit.json
  all     scan + inject 一步到位

六条确定性防御：
  1. 分层策略：强链（库里已有）正文首次注入；弱链（库里没有）默认收文末，可选正文或关闭
  2. 保护区隔离：frontmatter / 代码块 / 行内代码 / URL / Markdown链接 / 数学公式 / 标题行 / 已有 [[...]] 一律不动
  3. 幂等输出：从 raw.md 每次独立生成 final.md，不做原地叠加
  4. 精准词界：中文 term 前后排除 CJK+字母数字；英文用 \\b + IGNORECASE 词界
  5. 首次出现：每个术语在整篇正文仅注入一次，不污染阅读体验
  6. 长词优先：按术语长度降序匹配，彻底杜绝短词（如「动态」）切碎长词（如「动态规划」）

terms.json 接口契约：
  输入可以是 JSON 数组或包含 "terms" 键的对象：
  [
    {
      "term": "动态规划",                      // 必填：术语原始名称
      "type": "algorithm",                    // 可选：concept | algorithm | technique | data-structure
      "target": "01_算法/动态规划.md"         // 可选：指定精确 Vault 笔记 stem 或相对路径（消歧）
    }
  ]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

APP = "video2obsidian"
CACHE_ROOT = Path(os.environ.get("V2N_CACHE", Path.home() / ".cache" / APP))
DEFAULT_INDEX = CACHE_ROOT / "vault_index.json"

MIN_TERM_LEN = 2
MAX_TERM_LEN = 40
CONCEPT_TYPES = {"concept", "algorithm", "technique", "data-structure"}

STOPWORDS = {
    "问题", "方法", "时间", "数据", "情况", "方式", "结果", "过程", "系统",
    "功能", "内容", "时候", "地方", "东西", "意思", "例子", "大家", "同学",
    "我们", "你们", "他们", "这个", "那个", "什么", "怎么", "可以", "需要",
    "应该", "必须", "可能", "也许", "真的", "确实", "其实", "因为", "所以",
    "但是", "不过", "然而",
    "the", "a", "an", "and", "or", "but", "if", "of", "in", "on", "at",
    "to", "for", "with", "by", "is", "are", "was", "were",
}

CJK = r"\u4e00-\u9fff"
BOUND = rf"[{CJK}A-Za-z0-9_]"

# 保护区正则（优先级：长匹配/外层块优先）
PROTECTED_PATTERNS = [
    (re.compile(r"\A---\n.*?\n---\n", re.DOTALL), "frontmatter"),
    (re.compile(r"```[^\n]*\n.*?```", re.DOTALL), "codeblock"),
    (re.compile(r"`[^`\n]+`"), "inlinecode"),
    (re.compile(r"\[\[[^\]\n]+\]\]"), "wikilink"),
    (re.compile(r"\[[^\]\n]+\]\([^\)\n]+\)"), "mdlink"),
    (re.compile(r"https?://\S+"), "url"),
    (re.compile(r"\$\$.*?\$\$", re.DOTALL), "math"),
    (re.compile(r"\$[^$\n]+\$"), "mathinline"),
    (re.compile(r"^#{1,6}\s+[^\n]+$", re.MULTILINE), "heading"),
]


# ---------------------------------------------------------------- 段切分与保护区隔离

def split_protected(text: str) -> list[tuple[str, str]]:
    """把文档切成 [(kind, chunk), ...]，kind='text' 或各类受保护类型。"""
    spans = []
    for pat, kind in PROTECTED_PATTERNS:
        for m in pat.finditer(text):
            spans.append((m.start(), m.end(), kind))

    # 起点升序，同起点长的优先（避免 inline code 破坏 code block）
    spans.sort(key=lambda x: (x[0], -(x[1] - x[0])))

    merged = []
    for s, e, k in spans:
        if merged and s <= merged[-1][1]:
            ps, pe, pk = merged[-1]
            # 重叠时取并集覆盖全部保护区域，且继承较大跨度的保护类型
            if (e - s) > (pe - ps):
                merged[-1] = (min(s, ps), max(e, pe), k)
            else:
                merged[-1] = (min(s, ps), max(e, pe), pk)
        else:
            merged.append((s, e, k))

    out = []
    pos = 0
    for s, e, k in merged:
        if s > pos:
            out.append(("text", text[pos:s]))
        out.append((k, text[s:e]))
        pos = e
    if pos < len(text):
        out.append(("text", text[pos:]))
    return out


# ---------------------------------------------------------------- Vault 扫描与索引构建

def _parse_frontmatter(head: str) -> tuple[list[str], Optional[str]]:
    """从 frontmatter 提取 aliases 以及 title。"""
    aliases: list[str] = []
    title: Optional[str] = None
    m = re.match(r"\A---\n(.*?)\n---\n", head, re.DOTALL)
    if not m:
        return aliases, title
    fm = m.group(1)

    # 提取 title: "xxx"
    tm = re.search(r"^title\s*:\s*[\"']?([^\"'\n]+)[\"']?", fm, re.MULTILINE)
    if tm:
        title = tm.group(1).strip()

    # inline: aliases: [DP, Dynamic Programming]
    for am in re.finditer(r"aliases?\s*:\s*\[([^\]]*)\]", fm):
        for x in am.group(1).split(","):
            x = x.strip().strip("\"'")
            if x:
                aliases.append(x)

    # block list:
    # aliases:
    #   - DP
    #   - Dynamic Programming
    block = re.search(r"^aliases?\s*:\s*\n((?:[ \t]+-[ \t]*.+\n?)+)", fm, re.MULTILINE)
    if block:
        for line in block.group(1).splitlines():
            x = line.strip()
            if x.startswith("-"):
                x = x[1:].strip().strip("\"'")
                if x:
                    aliases.append(x)

    seen = set()
    out = []
    for a in aliases:
        if a not in seen:
            seen.add(a)
            out.append(a)
    return out, title


def scan_vault(vault_root: Path, prior_index: Optional[dict] = None) -> dict:
    """真正的增量扫描 Vault，以相对路径 rel 为主键，维护同名消歧映射表。"""
    old_files = prior_index.get("files", {}) if prior_index else {}
    old_notes = prior_index.get("notes", {}) if prior_index else {}

    notes: dict[str, dict] = {}
    name_index: dict[str, list[str]] = {}
    alias_index: dict[str, str] = {}
    files: dict[str, dict] = {}
    conflicts: list[dict] = []

    reused_count = 0
    parsed_count = 0
    found_rels = set()

    for md in sorted(vault_root.rglob("*.md")):
        rel_parts = md.relative_to(vault_root).parts
        if any(p.startswith(".") for p in rel_parts):
            continue
        try:
            st = md.stat()
        except OSError:
            continue

        rel = str(md.relative_to(vault_root)).replace("\\", "/")
        rel_stem = rel[:-3] if rel.endswith(".md") else rel
        found_rels.add(rel)
        files[rel] = {"mtime": st.st_mtime, "size": st.st_size}

        # 真正增量判断：mtime + size 均未变则直接复用旧索引数据，不读文件内容
        if (
            rel in old_files
            and old_files[rel].get("mtime") == st.st_mtime
            and old_files[rel].get("size") == st.st_size
            and rel in old_notes
        ):
            note_entry = old_notes[rel]
            reused_count += 1
        else:
            aliases: list[str] = []
            custom_title: Optional[str] = None
            try:
                with open(md, "r", encoding="utf-8", errors="ignore") as fh:
                    head = fh.read(4000)
                aliases, custom_title = _parse_frontmatter(head)
            except Exception:
                pass

            note_entry = {
                "rel_path": rel,
                "stem": md.stem,
                "rel_stem": rel_stem,
                "aliases": aliases,
            }
            if custom_title:
                note_entry["title"] = custom_title
            parsed_count += 1

        notes[rel] = note_entry

        # 建立多维度名称索引（短名、相对路径短名、title、aliases）
        stem = note_entry.get("stem", md.stem)
        names_to_map = [stem, rel_stem]
        if note_entry.get("title"):
            names_to_map.append(note_entry["title"])
        names_to_map.extend(note_entry.get("aliases", []))

        for name in names_to_map:
            if not name:
                continue
            if name not in name_index:
                name_index[name] = []
            if rel_stem not in name_index[name]:
                name_index[name].append(rel_stem)

    removed_count = len(old_files) - len(found_rels & set(old_files.keys())) if old_files else 0

    # 建立确定性 alias_index：唯一命中直接映射；同名冲突记录进 conflicts 供消歧审计
    for name, targets in name_index.items():
        if len(targets) == 1:
            alias_index[name] = targets[0]
        else:
            conflicts.append({"name": name, "candidates": targets})
            # 发生歧义时，短名默认指向更完整的相对路径格式以防混淆
            alias_index[name] = targets[0]

    return {
        "vault_root": str(vault_root),
        "generated_at": time.time(),
        "files": files,
        "notes": notes,
        "name_index": name_index,
        "alias_index": alias_index,
        "alias_conflicts": conflicts,
        "scan_stats": {
            "reused": reused_count,
            "parsed": parsed_count,
            "removed": max(0, removed_count),
        },
    }


# ---------------------------------------------------------------- 术语合规过滤与词界正则

def is_valid_term(term: str) -> bool:
    """对 LLM 输出的候选术语进行严格兜底过滤。"""
    if not term or not (MIN_TERM_LEN <= len(term) <= MAX_TERM_LEN):
        return False
    if term in STOPWORDS or term.lower() in STOPWORDS:
        return False
    # 过滤纯标点、异常字符，保留中英文、数字、连字符、点和下划线
    if not re.match(r"^[\w\u4e00-\u9fff\-\./\+]+$", term):
        return False
    return True


def build_term_pattern(term: str) -> re.Pattern:
    """构造安全词界正则：英文严格匹配 \\b 词界与忽略大小写；中文/混合词前后排除英数标识符以防截断。"""
    escaped = re.escape(term)
    if term.isascii():
        return re.compile(rf"\b{escaped}\b", re.IGNORECASE)
    return re.compile(rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])")


def target_exists_in_index(target: str, index: dict) -> bool:
    """严格检验目标笔记是否真正在 Vault 索引中存在（支持相对路径、文件名、别名，支持大小写不敏感回退）。"""
    if not target or not index:
        return False
    notes = index.get("notes", {})
    name_index = index.get("name_index", {})
    files = index.get("files", {})

    target_clean = str(target).replace("\\", "/")
    target_md = target_clean if target_clean.endswith(".md") else f"{target_clean}.md"

    # 1. 相对路径（如 "算法/DFS.md" 或 "算法/DFS"）精确命中
    if target_md in notes or target_md in files:
        return True
    if any(n.get("rel_stem") == target_clean or n.get("stem") == target_clean for n in notes.values()):
        return True

    # 2. 标题 / 别名 / 名称索引精确命中
    if target in name_index and len(name_index[target]) > 0:
        return True

    # 3. 大小写不敏感回退匹配（解决 dfs.md vs [[DFS]] 等常见场景）
    target_lower = target.lower()
    target_md_lower = target_md.lower()
    target_clean_lower = target_clean.lower()
    if any(k.lower() == target_md_lower for k in notes.keys()) or any(k.lower() == target_md_lower for k in files.keys()):
        return True
    if any(n.get("rel_stem", "").lower() == target_clean_lower or n.get("stem", "").lower() == target_clean_lower for n in notes.values()):
        return True
    for name, candidates in name_index.items():
        if name.lower() == target_lower and len(candidates) > 0:
            return True

    return False


# ---------------------------------------------------------------- 链接注入逻辑

def inject_into_segment(
    text: str,
    terms: list[dict],
    name_index: dict,
    index: dict,
    linked: set,
    weak_mode: str,
    audit: dict,
) -> str:
    """在非保护正文段中执行长术语优先的首次链接注入，支持 LLM target 强校验与歧义不乱链。"""
    curr_segments: list[tuple[str, str]] = [("text", text)]

    for t in terms:
        term = t["term"]
        if term in linked:
            continue

        # 1. 优先使用 LLM 语义层指定的 target（必须校验在 Vault 中真实存在）
        target = t.get("target")
        if target:
            if target_exists_in_index(target, index):
                kind = "strong"
            else:
                # 目标在 Vault 中不存在！宁可少打一条链接，绝不制造假知识节点
                audit["invalid_targets"].append({"term": term, "target": target})
                continue
        elif term in name_index:
            candidates = name_index[term]
            if len(candidates) == 1:
                target = candidates[0]
                kind = "strong"
            else:
                # 多个目标：歧义时宁可不链接，也不要链接错！
                audit["ambiguous_terms"].append({"term": term, "candidates": candidates})
                continue
        elif t.get("type") in CONCEPT_TYPES:
            if weak_mode != "body":
                continue
            kind = "weak"
            target = term
        else:
            continue

        pat = build_term_pattern(term)
        new_segments = []
        found = False

        for seg_kind, seg_text in curr_segments:
            if found or seg_kind != "text":
                new_segments.append((seg_kind, seg_text))
                continue

            m = pat.search(seg_text)
            if m and not found:
                matched_text = m.group(0)
                display_text = matched_text
                link_target = target
                if "/" in link_target:
                    replacement = f"[[{link_target}|{display_text}]]"
                else:
                    replacement = f"[[{display_text}]]" if link_target == display_text else f"[[{link_target}|{display_text}]]"

                before = seg_text[: m.start()]
                after = seg_text[m.end():]
                if before:
                    new_segments.append(("text", before))
                new_segments.append(("wikilink", replacement))
                if after:
                    new_segments.append(("text", after))
                found = True
                linked.add(term)
                audit[f"{kind}_links"] += 1
                audit["linked_terms"].append(term)
            else:
                new_segments.append((seg_kind, seg_text))
        curr_segments = new_segments

    return "".join(s[1] for s in curr_segments)


def build_ambiguous_footer(ambiguous_terms: list[dict]) -> str:
    """当存在同名歧义且未获 LLM 指定目标时，在文末列出提示而非正文乱链。"""
    if not ambiguous_terms:
        return ""
    lines = ["\n\n## ⚠️ 知识消歧提示\n"]
    for item in ambiguous_terms:
        term = item["term"]
        cands = "、".join([f"`{c}`" for c in item.get("candidates", [])])
        lines.append(f"- **{term}**：知识库中存在多个同名节点（{cands}），已跳过正文强链（可通过 LLM 术语表指定 `target`）")
    return "\n".join(lines) + "\n"


def build_weak_footer(weak_terms: list[str]) -> str:
    """生成文末弱链接区域，为未来笔记铺路而不污染正文。"""
    if not weak_terms:
        return ""
    lines = ["\n\n## 🔗 关联概念\n"]
    for t in sorted(weak_terms):
        lines.append(f"- [[{t}]]")
    return "\n".join(lines) + "\n"


def inject_document(
    raw_md: str,
    terms: list[dict],
    index: dict,
    options: dict,
) -> tuple[str, dict]:
    """主注入函数，返回 (处理后内容, 审计指标字典)。"""
    alias_index = index.get("alias_index", {})
    name_index = index.get("name_index", {})
    weak_mode = options.get("weak_links", "footer")

    audit = {
        "terms_input": len(terms),
        "strong_links": 0,
        "weak_links": 0,
        "weak_footer": 0,
        "skipped_not_in_text": 0,
        "skipped_invalid": 0,
        "linked_terms": [],
        "invalid_targets": [],
        "ambiguous_terms": [],
    }

    valid = []
    for t in terms:
        term = t.get("term", "")
        if not is_valid_term(term):
            audit["skipped_invalid"] += 1
            continue
        valid.append(t)

    # 关键：按字符长度降序排序，确保「动态规划」优先于「动态」被匹配
    valid.sort(key=lambda t: -len(t["term"]))

    linked: set = set()
    segments = split_protected(raw_md)
    parts = []
    for kind, chunk in segments:
        if kind == "text":
            chunk = inject_into_segment(chunk, valid, name_index, index, linked, weak_mode, audit)
        parts.append(chunk)
    final = "".join(parts)

    # 统计未能匹配进正文的术语数
    audit["skipped_not_in_text"] = len(valid) - len(linked)

    # 弱链接放入文末
    if weak_mode == "footer":
        seen = set()
        weak_final = []
        for t in valid:
            term = t["term"]
            if term in alias_index or term in linked:
                continue
            if t.get("type") not in CONCEPT_TYPES:
                continue
            if term in seen:
                continue
            seen.add(term)
            weak_final.append(term)
        if weak_final:
            final += build_weak_footer(weak_final)
            audit["weak_footer"] = len(weak_final)

    # 存在歧义的术语在文末统一展示，防范误链（仅在允许追加页脚时展示，当 weak_mode=none 时遵从纯净正文语义）
    if audit["ambiguous_terms"] and weak_mode != "none":
        final += build_ambiguous_footer(audit["ambiguous_terms"])

    return final, audit


# ---------------------------------------------------------------- CLI 命令行封装

def cmd_scan(args) -> int:
    vault = Path(args.vault)
    if not vault.is_dir():
        print(f"[error] Vault 目录不存在: {vault}", file=sys.stderr)
        return 2
    idx_path = Path(args.index)
    prior_index = None
    if idx_path.exists():
        try:
            prior_index = json.loads(idx_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    print(f"[scan] 开始扫描 Vault: {vault}", file=sys.stderr)
    t0 = time.time()
    index = scan_vault(vault, prior_index=prior_index)
    idx_path.parent.mkdir(parents=True, exist_ok=True)
    idx_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    stats = index.get("scan_stats", {})
    print(
        f"[scan] 完成：{len(index['notes'])} 笔记 / {len(index['alias_index'])} 别名 / "
        f"{len(index['alias_conflicts'])} 冲突（增量复用 {stats.get('reused', 0)}，重新解析 {stats.get('parsed', 0)}，移除 {stats.get('removed', 0)}，耗时 {time.time() - t0:.2f}s）→ {idx_path}",
        file=sys.stderr,
    )
    return 0


def cmd_inject(args, index: Optional[dict] = None) -> int:
    idx_path = Path(args.index)
    if index is None:
        if not idx_path.exists():
            print(f"[error] 索引不存在，请先运行 scan 生成索引：{idx_path}", file=sys.stderr)
            return 2
        index = json.loads(idx_path.read_text(encoding="utf-8"))

    terms_path = Path(args.terms)
    if not terms_path.exists():
        print(f"[error] 术语文件不存在: {terms_path}", file=sys.stderr)
        return 2
    raw = json.loads(terms_path.read_text(encoding="utf-8"))
    terms = raw if isinstance(raw, list) else raw.get("terms", [])

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"[error] 输入文件不存在: {in_path}", file=sys.stderr)
        return 2

    md = in_path.read_text(encoding="utf-8")
    final, audit = inject_document(md, terms, index, {"weak_links": args.weak_links})

    if args.inplace:
        out_path = in_path
    else:
        if not args.output:
            print("[error] 非 inplace 模式必须指定 --output", file=sys.stderr)
            return 2
        out_path = Path(args.output)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(final, encoding="utf-8")

    audit.update({
        "input": str(in_path),
        "output": str(out_path),
        "index_notes": len(index.get("notes", {})),
        "weak_links_mode": args.weak_links,
    })
    if args.audit:
        a_path = Path(args.audit)
        a_path.parent.mkdir(parents=True, exist_ok=True)
        a_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")

    amb_msg = f" | 歧义消歧: {len(audit['ambiguous_terms'])}" if audit["ambiguous_terms"] else ""
    print(
        f"[inject] 强链: {audit['strong_links']} | 弱链正文: {audit['weak_links']} | "
        f"弱链文末: {audit['weak_footer']} | 无效术语: {audit['skipped_invalid']} | "
        f"正文未现: {audit['skipped_not_in_text']}{amb_msg}",
        file=sys.stderr,
    )
    return 0


def cmd_all(args) -> int:
    vault = Path(args.vault)
    if not vault.is_dir():
        print(f"[error] Vault 目录不存在: {vault}", file=sys.stderr)
        return 2
    idx_path = Path(args.index)
    prior_index = None
    if idx_path.exists():
        try:
            prior_index = json.loads(idx_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    index = scan_vault(vault, prior_index=prior_index)
    idx_path.parent.mkdir(parents=True, exist_ok=True)
    idx_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return cmd_inject(args, index=index)


def main() -> int:
    ap = argparse.ArgumentParser(description="wikify — Vault 索引与 Wikilinks 幂等注入引擎")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="扫描 Vault 建立索引缓存")
    p_scan.add_argument("--vault", required=True, help="Obsidian Vault 根目录")
    p_scan.add_argument("--index", default=str(DEFAULT_INDEX), help="索引缓存保存路径")

    p_inject = sub.add_parser("inject", help="对 Markdown 正文注入 Wikilinks")
    p_inject.add_argument("--terms", required=True, help="术语候选 JSON（LLM 输出）")
    p_inject.add_argument("--input", required=True, help="待处理原始 markdown 文件")
    p_inject.add_argument("--output", default=None, help="输出文件路径")
    p_inject.add_argument("--index", default=str(DEFAULT_INDEX), help="索引文件路径")
    p_inject.add_argument("--audit", default=None, help="审计结果 JSON 输出路径")
    p_inject.add_argument("--weak-links", choices=["body", "footer", "none"], default="footer")
    p_inject.add_argument("--inplace", action="store_true", help="原地修改输入文件")

    p_all = sub.add_parser("all", help="一步到位：扫描 Vault 并注入")
    p_all.add_argument("--vault", required=True, help="Obsidian Vault 根目录")
    p_all.add_argument("--terms", required=True, help="术语候选 JSON")
    p_all.add_argument("--input", required=True, help="输入 Markdown")
    p_all.add_argument("--output", default=None, help="输出 Markdown")
    p_all.add_argument("--index", default=str(DEFAULT_INDEX))
    p_all.add_argument("--audit", default=None)
    p_all.add_argument("--weak-links", choices=["body", "footer", "none"], default="footer")
    p_all.add_argument("--inplace", action="store_true")

    args = ap.parse_args()
    if args.cmd == "scan":
        return cmd_scan(args)
    if args.cmd == "inject":
        return cmd_inject(args)
    if args.cmd == "all":
        return cmd_all(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
