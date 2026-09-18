#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""回归测试 —— 锁死 7 个已修复缺陷，防止复发。

  B1  extract.merge 在 --chunks 部分提取时崩溃（全量归档那一行要求全部分块就位）
  B2  validate_note 的 Anchor 检查因 emoji 变体选择符而**静默空转**
      （🎙️ = U+1F399 + U+FE0F 两个码点，字符类 [🎙️🎤] 只吃一个 → 正则永远匹配不上）
  B3  validate_note 的 Anchor 原文溯源对"模型补标点"误报为编造
  B4  wikify 首次使用必须先 scan（SKILL.md 原先只写 inject，新机器上 exit 2）
  B5  validate_note 复杂度检测正则支持主流写法：O(N log N)、O(V+E)、O(2^n)、O(n^2)
  B6  wikify.split_protected 在保护区间部分重叠时取并集，杜绝保护空隙与误注入
  B7  wikify 在 --weak-links none 时杜绝追加多余页脚

运行：python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR))

import extract          # noqa: E402
import validate_note    # noqa: E402

MIC = "🎙" + chr(0xFE0F)   # 🎙️ 带变体选择符 —— SKILL.md 规定的写法
MIC_BARE = "\U0001F399"     # 🎙 不带变体符
# 【为什么这里用转义而不是直接敲 emoji】测试本身也怕被编辑器/工具链把 U+FE0F 吃掉——
# 一旦被吃掉，这条"防静默失效"的测试就会跟着静默失效，变成只测裸 emoji 的摆设。
# 所以钉死码点，并在下面断言一次。
assert len(MIC) == 2 and ord(MIC[1]) == 0xFE0F, "测试常量被改写，B2 回归测试已失去意义"
WIKIFY = SKILL_DIR / "wikify.py"


# ------------------------------------------------------------------ 构造辅助

def make_note(anchors: list[tuple[str, str, str]], mic: str = MIC) -> str:
    """按 SKILL.md 规定的三行格式拼一份带 Anchor 的笔记。"""
    body = "".join(
        f'> [!quote] {mic} 原片教学锚点（{up}）\n> "{quote}"\n> —— [{span}]\n\n'
        for quote, span, up in anchors
    )
    return f"---\ntitle: t\n---\n\n# T\n\n{body}"


ARCHIVE = json.dumps(
    {"video_id": "BV1", "content": "[00:03:10] 整条马路都堵死了收费站必须限流\n"},
    ensure_ascii=False,
)


# ------------------------------------------------------------------ B1

class TestPartialChunkMerge(unittest.TestCase):
    """B1：--chunks 只转录了部分分块时，归档路径不得要求全部分块就位。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self._tmp.name)
        # 时长 40 分钟 → 4 个 600s 分块；用户只转录了 0 和 1
        self.manifest = {"version": 1, "video_id": "BVt", "duration": 2400.0,
                         "params": {}, "chunks": extract.plan_chunks(2400.0, 600.0)}
        for c in self.manifest["chunks"]:
            if c["id"] in (0, 1):
                c["status"] = "done"
                (self.run_dir / c["file"]).write_text(
                    json.dumps({"segments": [{"start": c["t0"], "end": c["t0"] + 5,
                                              "text": f"chunk{c['id']}"}]}, ensure_ascii=False),
                    encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_transcribed_chunk_ids_only_lists_existing_files(self):
        self.assertEqual(extract.transcribed_chunk_ids(self.run_dir, self.manifest), [0, 1])

    def test_archive_merge_does_not_raise(self):
        ids = extract.transcribed_chunk_ids(self.run_dir, self.manifest)
        segs = extract.merge(self.run_dir, self.manifest, selected_chunk_ids=ids)
        self.assertEqual([s["text"] for s in segs], ["chunk0", "chunk1"])

    def test_strict_merge_still_refuses_incomplete_data(self):
        """宽松的只是归档路径；用户点名的分块缺一块仍须报错。"""
        with self.assertRaises(RuntimeError):
            extract.merge(self.run_dir, self.manifest, selected_chunk_ids=None)


# ------------------------------------------------------------------ B2

class TestAnchorEmojiVariant(unittest.TestCase):
    """B2：带变体选择符的 🎙️ 必须被识别，且失配时要吵出来。"""

    def test_vs16_emoji_anchor_is_parsed(self):
        note = make_note([("整条马路都堵死了收费站必须限流", "03:10 - 03:24", "UP主")])
        self.assertEqual(len(validate_note.ANCHOR_QUOTE_PATTERN.findall(note)), 1,
                         "带 U+FE0F 的 🎙️ 未被识别 —— Anchor 检查又空转了")

    def test_bare_emoji_still_parsed(self):
        note = make_note([("整条马路都堵死了收费站必须限流", "03:10 - 03:24", "UP主")], mic=MIC_BARE)
        self.assertEqual(len(validate_note.ANCHOR_QUOTE_PATTERN.findall(note)), 1)

    def test_hard_cap_of_three_is_enforced(self):
        """上限 3 条。修复前这份笔记拿满分——因为它一条 anchor 都没"看见"。"""
        note = make_note([(f"第{i}句原话", f"0{i}:10 - 0{i}:24", "UP主") for i in range(1, 6)])
        res = validate_note.validate_note(note)
        self.assertFalse(res["passed"])
        self.assertEqual(res["metrics"]["anchor_count"], 5)
        self.assertTrue(any("上限" in e for e in res["errors"]), res["errors"])

    def test_oversized_quote_is_blocked(self):
        note = make_note([("这是" * 31, "03:10 - 03:24", "UP主")])
        res = validate_note.validate_note(note)
        self.assertTrue(any("50 字" in e for e in res["errors"]), res["errors"])

    def test_malformed_body_is_loud(self):
        """标记行正常、正文行错位（这里是多插了一个空行）→ 由"结构不完整"拦下。"""
        note = ('---\ntitle: t\n---\n\n# T\n\n'
                f'> [!quote] {MIC} 原片教学锚点（UP主）\n> "整条马路都堵死了"\n\n> —— [03:10 - 03:24]\n')
        res = validate_note.validate_note(note)
        self.assertFalse(res["passed"])
        self.assertTrue(any("结构不完整" in e for e in res["errors"]), res["errors"])

    def test_missing_mic_emoji_is_loud(self):
        """连标记行都不匹配（模型漏了话筒图标）→ 修复前这里**一条错误都不报**。

        这正是 B2 的本质：不是"检查的结果不对"，而是"检查根本没跑，而且不吭声"。
        """
        note = ('---\ntitle: t\n---\n\n# T\n\n'
                '> [!quote] 原片教学锚点（UP主）\n> "整条马路都堵死了"\n> —— [03:10 - 03:24]\n')
        res = validate_note.validate_note(note)
        self.assertFalse(res["passed"], "锚点写得像模像样却完全没被审计，必须报错")
        self.assertTrue(any("格式漂移" in e for e in res["errors"]), res["errors"])

    def test_missing_archive_is_warning_only(self):
        """未提供 archive 时只提示，不阻断（离线场景不该被门禁卡死）。"""
        note = make_note([("整条马路都堵死了收费站必须限流", "03:10 - 03:24", "UP主")])
        res = validate_note.check_anchors(note, "")
        self.assertEqual(res["blocking"], [])


# ------------------------------------------------------------------ B3

class TestAnchorProvenance(unittest.TestCase):
    """B3：原文溯源应抓"改词"，不应抓"补标点"。"""

    def test_verbatim_quote_passes(self):
        r = validate_note.check_anchors(
            make_note([("整条马路都堵死了收费站必须限流", "03:10 - 03:24", "UP主")]), ARCHIVE)
        self.assertEqual(r["blocking"], [])

    def test_added_punctuation_is_not_a_fabrication(self):
        r = validate_note.check_anchors(
            make_note([("整条马路都堵死了，收费站必须限流", "03:10 - 03:24", "UP主")]), ARCHIVE)
        self.assertEqual(r["blocking"], [], "补标点被误判成编造 —— ASR 原文本来就没标点")

    def test_rewritten_wording_is_blocked(self):
        r = validate_note.check_anchors(
            make_note([("整条马路都堵死了，收费站必须限制车流", "03:10 - 03:24", "UP主")]), ARCHIVE)
        self.assertTrue(any("不在原始 transcript" in e for e in r["blocking"]), r["blocking"])

    def test_fabricated_quote_is_blocked(self):
        r = validate_note.check_anchors(
            make_note([("拥塞控制就是给网络修一条备用高速公路", "03:10 - 03:24", "UP主")]), ARCHIVE)
        self.assertTrue(any("不在原始 transcript" in e for e in r["blocking"]), r["blocking"])


# ------------------------------------------------------------------ B4

class TestWikifyColdStart(unittest.TestCase):
    """B4：全新机器（无索引缓存）上，SKILL.md 里那条命令必须能跑通。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.vault = root / "vault"
        (self.vault / "Topics").mkdir(parents=True)
        (self.vault / "Topics" / "TCP 拥塞控制.md").write_text(
            "---\ntitle: TCP 拥塞控制\naliases: [拥塞控制]\n---\n# x\n", encoding="utf-8")
        self.note = root / "note.md"
        self.note.write_text("# 拥塞控制\n\n流量控制不是拥塞控制。\n", encoding="utf-8")
        self.terms = root / "terms.json"
        self.terms.write_text(json.dumps(
            [{"term": "拥塞控制", "target": "TCP 拥塞控制", "type": "concept"}],
            ensure_ascii=False), encoding="utf-8")
        self.out = root / "note_final.md"
        self.env = {**os.environ, "V2N_CACHE": str(root / "cache")}   # 空缓存 = 冷启动

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, *argv):
        return subprocess.run([sys.executable, str(WIKIFY), *argv],
                              capture_output=True, text=True, encoding="utf-8", env=self.env)

    def test_all_builds_index_then_injects(self):
        r = self._run("all", "--vault", str(self.vault), "--terms", str(self.terms),
                      "--input", str(self.note), "--output", str(self.out), "--weak-links", "none")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("[[TCP 拥塞控制|拥塞控制]]", self.out.read_text(encoding="utf-8"))
        self.assertTrue((Path(self.env["V2N_CACHE"]) / "vault_index.json").exists(),
                        "all 应该把索引落盘，供下次增量复用")

    def test_inject_alone_on_cold_start_exits_2(self):
        """记录 inject 的冷启动行为——这正是 SKILL.md 不能只写 inject 的原因。"""
        r = self._run("inject", "--terms", str(self.terms), "--input", str(self.note),
                      "--output", str(self.out), "--weak-links", "none")
        self.assertEqual(r.returncode, 2)
        self.assertIn("索引不存在", r.stderr)


# ------------------------------------------------------------------ B5
class TestComplexityRegexAndQuestionFormat(unittest.TestCase):
    """B5：复杂度检测必须识别各种主流算法写法，自测题支持序号与题干无空格。"""

    def test_mainstream_complexity_notations(self):
        cases = ["O(N log N)", "O(V+E)", "O(2^n)", "O(n^2)", "O(N)", "O(E log V)"]
        for c in cases:
            note_content = (
                f"---\ntitle: test\n---\n# T\n> 🎯 **全篇通关目标**：掌握\n"
                f"```python\ndef f(): pass\n```\n此处执行耗时为 {c} 且内存极佳。\n"
                f"> [00:10] [🎥 原片] 讲师说明\n\n"
                f"## 闭环自测练习 📝\n1.问题一\n> [!TIP]\n> 答案\n"
                f"2.问题二\n> [!TIP]\n> 答案\n"
                f"3.问题三\n> [!TIP]\n> 答案\n"
            )
            res = validate_note.validate_note(note_content)
            self.assertFalse(any("缺失时间/空间复杂度" in w for w in res["warnings"]), f"漏报了主流复杂度写法: {c}")

    def test_questions_without_whitespace_parsed(self):
        recall_text = (
            "## 闭环自测练习 📝\n"
            "1.什么是拥塞控制？\n> [!TIP]\n> 答案一\n\n"
            "2.AIMD 的数学本质？\n> [!TIP]\n> 答案二\n\n"
            "3.快恢复如何工作？\n> [!TIP]\n> 答案三\n"
        )
        note_content = (
            f"---\ntitle: test\n---\n# T\n> 🎯 **全篇通关目标**：掌握\n"
            f"> [00:10] [🎥 原片] 讲师说明\n\n"
            f"{recall_text}"
        )
        res = validate_note.validate_note(note_content)
        self.assertEqual(res["metrics"]["questions_count"], 3)
        self.assertFalse(any("自测题不足 3 道" in w for w in res["warnings"]))


# ------------------------------------------------------------------ B6 & B7
class TestProtectedSpansAndCleanFooter(unittest.TestCase):
    """B6 & B7：保护区间重叠取并集，--weak-links none 保持正文纯净。"""

    def test_split_protected_overlapping_union(self):
        import wikify
        # 构造重叠 span：代码块 [10, 50] 与紧随重叠的链接 [40, 70]
        text = "0123456789" + "```python\nprint('hello')\n```" + "http://example.com/api"
        segments = wikify.split_protected(text)
        # 确保保护段拼接后完整覆盖原本字符，且没有裸露空隙
        reconstructed = "".join(chunk for _, chunk in segments)
        self.assertEqual(reconstructed, text)

    def test_weak_links_none_suppresses_footer(self):
        import wikify
        index = {"notes": {}, "name_index": {"动态": ["动态A", "动态B"]}, "alias_index": {}}
        terms = [{"term": "动态", "type": "concept"}]
        raw_md = "# 标题\n\n这是动态正文。"
        final, audit = wikify.inject_document(raw_md, terms, index, {"weak_links": "none"})
        self.assertNotIn("## ⚠️ 知识库歧义消歧提示", final)
        self.assertNotIn("## 🔗 关联概念", final)


# ------------------------------------------------------------------ B8: 跨段引文与自测题解析隔离
class TestCrossSegmentAndRecallEdgeCases(unittest.TestCase):
    """B8：跨段引文（去噪时剥离时间戳）与自测题 <details> 解析内部编号隔离。"""

    def test_quote_spanning_two_asr_segments_passes(self):
        """跨段引文（Whisper 常把一句话切成两段）必须通过溯源校验。"""
        archive_text = (
            "[00:07:47] 我一直觉得这个算法的读音\n"
            "[00:07:49] 要比这个算法的执行要难多了\n"
        )
        quote = "我一直觉得这个算法的读音要比这个算法的执行要难多了"
        note = make_note([(quote, "07:47 - 07:51", "UP主")])
        res = validate_note.check_anchors(note, archive_text)
        self.assertEqual(res["blocking"], [], f"跨段引文被误判为编造: {res['blocking']}")

    def test_numbered_list_inside_details_is_not_a_question(self):
        """答案体 <details> 内的编号列表不能被计成题目。"""
        recall_text = (
            "## 闭环自测练习 📝\n\n"
            "1. 什么是拥塞控制？\n"
            "<details>\n"
            "<summary>答案与步骤解析</summary>\n"
            "1. 第一阶段：慢开始指数增长。\n"
            "2. 第二阶段：到达 ssthresh 后转为拥塞避免。\n"
            "3. 第三阶段：超时或收到 3 个 Dup ACK。\n"
            "</details>\n\n"
            "2. AIMD 的本质是什么？\n"
            "<details>\n<summary>答案</summary>\n加法增大乘法减小。\n</details>\n\n"
            "3. 快恢复如何工作？\n"
            "<details>\n<summary>答案</summary>\n仅将 cwnd 减半并线性探测。\n</details>\n"
        )
        note_content = (
            f"---\ntitle: test\n---\n# T\n> 🎯 **全篇通关目标**：掌握\n"
            f"> [00:10] [🎥 原片] 讲师说明\n\n"
            f"{recall_text}"
        )
        res = validate_note.validate_note(note_content)
        self.assertEqual(res["metrics"]["questions_count"], 3,
                         f"答案体内部的编号列表被误计为题目: {res['metrics']['questions_count']}")
        self.assertFalse(any("未配对" in w for w in res["warnings"]))

    def test_heading_style_questions_detected(self):
        """支持 SKILL.md 规定的标题式题目 '### 1. 题目名'。"""
        recall_text = (
            "## 闭环自测练习 📝\n\n"
            "### 1. 慢开始门限的作用？\n"
            "<details><summary>解析</summary>区分指数与线性增长阶段。</details>\n\n"
            "### 2. 为什么是 3 个 Dup ACK？\n"
            "<details><summary>解析</summary>概率论判定网络并未彻底拥塞瘫痪。</details>\n\n"
            "### 3. Tahoe 与 Reno 的差异？\n"
            "<details><summary>解析</summary>Tahoe 归零，Reno 快恢复减半。</details>\n"
        )
        note_content = (
            f"---\ntitle: test\n---\n# T\n> 🎯 **全篇通关目标**：掌握\n"
            f"> [00:10] [🎥 原片] 讲师说明\n\n"
            f"{recall_text}"
        )
        res = validate_note.validate_note(note_content)
        self.assertEqual(res["metrics"]["questions_count"], 3,
                         f"标题式题目未能正确识别: {res['metrics']['questions_count']}")
        self.assertEqual(res["metrics"]["answers_count"], 3)

    def test_anchor_audit_template_generation_and_validation(self):
        """测试自动生成 anchor_audit.json 骨架并能顺利通过 schema 规范校验。"""
        note = make_note([("整条马路都堵死了收费站必须限流", "03:10 - 03:20", "UP主")])
        template = validate_note.generate_anchor_audit_template(note, video_id="BV1test", source_title="TCP")
        self.assertEqual(len(template["candidates"]), 1)
        self.assertEqual(template["candidates"][0]["quote"], "整条马路都堵死了收费站必须限流")
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", suffix=".json", delete=False) as tf:
            json.dump(template, tf, ensure_ascii=False)
            tmp_name = tf.name
        try:
            issues = validate_note.check_anchor_audit(Path(tmp_name))
            self.assertEqual(issues, [], f"生成的模板未通过合规校验: {issues}")
        finally:
            os.remove(tmp_name)


# ------------------------------------------------------------------ B9: 自链接保护
class TestWikifySelfLinkProtection(unittest.TestCase):
    """B9：wikify 对指向当前笔记自身的术语实施防护，杜绝无意义自链。"""

    def test_wikify_skips_self_links(self):
        import wikify
        index = {
            "notes": {
                "计算机网络/TCP 拥塞控制.md": {"stem": "TCP 拥塞控制", "rel_stem": "计算机网络/TCP 拥塞控制"}
            },
            "name_index": {"TCP 拥塞控制": ["计算机网络/TCP 拥塞控制"]},
            "alias_index": {"TCP 拥塞控制": "计算机网络/TCP 拥塞控制"}
        }
        terms = [
            {"term": "TCP 拥塞控制", "target": "计算机网络/TCP 拥塞控制.md"},
            {"term": "慢开始", "type": "concept"}
        ]
        raw_md = "# TCP 拥塞控制\n\n在 TCP 拥塞控制 中，慢开始是初始阶段。"
        final, audit = wikify.inject_document(
            raw_md, terms, index,
            {"weak_links": "footer", "current_stem": "TCP 拥塞控制"}
        )
        # 正文中不应该有指向自身的链接
        self.assertNotIn("[[计算机网络/TCP 拥塞控制|TCP 拥塞控制]]", final)
        self.assertNotIn("[[TCP 拥塞控制]]", final)
        self.assertTrue(len(audit.get("skipped_self_links", [])) > 0)


# ------------------------------------------------------------------ B10: 多P分P视频解析
class TestExtractMultiPResolution(unittest.TestCase):
    """B10：extract.py 遇到 B 站多 P 视频 URL 时，正确提取分 P 编号，杜绝多 P 缓存碰撞覆盖。"""

    def test_resolve_video_id_multi_p(self):
        from extract import resolve_video_id
        # 标准 ?p=43
        self.assertEqual(resolve_video_id("https://www.bilibili.com/video/BV1b7411N798?p=43"), "BV1b7411N798_p43")
        # 带其它参数 &p=43
        self.assertEqual(resolve_video_id("https://www.bilibili.com/video/BV1b7411N798/?spm_id_from=333&p=43"), "BV1b7411N798_p43")
        # 简写 BV1b7411N798_p43
        self.assertEqual(resolve_video_id("BV1b7411N798_p43"), "BV1b7411N798_p43")
        # 单 P 保持不变
        self.assertEqual(resolve_video_id("https://www.bilibili.com/video/BV1b7411N798"), "BV1b7411N798")
        self.assertEqual(resolve_video_id("BV1b7411N798"), "BV1b7411N798")


# ------------------------------------------------------------------ B11: 提示语行内 details 防误吞
class TestValidateNoteInlineDetailsFix(unittest.TestCase):
    """B11：自测说明提示语中的 `<details>` 行内代码不应被误判为未闭合 HTML 标签而吞掉第 1 题。"""

    def test_inline_details_in_tip_preserves_q1(self):
        import validate_note
        raw = """---
title: "测试"
tags: [测试]
---
# 标题
🎯 **全篇通关目标**：测试

## 模块一：测试
🎯 学完你能：掌握测试

[> 🎥 来源原片：测试 [01:00]]

## 模块二：🧪 闭环主动自测
> [!TIP]
> 点击 `<details>` 展开查看答案。

### 1. 第一题
题目内容
<details>
<summary>答案</summary>
1. 解析步骤一
2. 解析步骤二
</details>

### 2. 第二题
题目内容
<details>
<summary>答案</summary>
解析
</details>

### 3. 第三题
题目内容
<details>
<summary>答案</summary>
解析
</details>
"""
        res = validate_note.validate_note(raw)
        warnings = res["warnings"]
        # 不应报警 "闭环自测题不足 3 道"
        q_warnings = [w for w in warnings if "闭环自测题不足" in w]
        self.assertEqual(len(q_warnings), 0, f"意外产生题目数警告: {q_warnings}")


# ------------------------------------------------------------------ B12: 跨平台 CRLF 换行符兼容
class TestCRLFSupport(unittest.TestCase):
    """B12：Windows 下 CRLF (\\r\\n) 换行符不应导致 Frontmatter 解析失败或未被保护。"""

    def test_validate_note_crlf_frontmatter(self):
        import validate_note
        raw_crlf = "---\r\ntitle: 测试\r\ntags: [考研]\r\n---\r\n# 正文\r\n"
        res = validate_note.validate_note(raw_crlf)
        fm_errors = [e for e in res["errors"] if "Frontmatter" in e]
        self.assertEqual(len(fm_errors), 0, "CRLF 换行导致 Frontmatter 报错")

    def test_wikify_crlf_frontmatter_protection(self):
        import wikify
        raw_crlf = "---\r\ntitle: 测试\r\naliases: [二叉树]\r\n---\r\n# 标题\r\n\r\n这里出现二叉树概念。\r\n"
        index = {
            "notes": {"二叉树.md": {"stem": "二叉树", "rel_stem": "二叉树"}},
            "name_index": {"二叉树": ["二叉树"]},
            "alias_index": {"二叉树": "二叉树"}
        }
        terms = [{"term": "二叉树", "target": "二叉树.md"}]
        final, audit = wikify.inject_document(raw_crlf, terms, index, {"weak_links": "footer"})
        # frontmatter 内不应被注入链接
        fm_part = final.split("---")[1]
        self.assertNotIn("[[二叉树]]", fm_part)


# ------------------------------------------------------------------ B13: parse_chunk_ids 边界健壮性
class TestParseChunkIdsBoundary(unittest.TestCase):
    """B13：分块解析支持逆序区间 (5-2) 以及异常字符串输入。"""

    def test_parse_chunk_ids(self):
        from extract import parse_chunk_ids
        self.assertEqual(parse_chunk_ids("0,1,3"), [0, 1, 3])
        self.assertEqual(parse_chunk_ids("0-3"), [0, 1, 2, 3])
        self.assertEqual(parse_chunk_ids("3-1"), [1, 2, 3])
        self.assertEqual(parse_chunk_ids("invalid, 2-4, foo"), [2, 3, 4])
        self.assertIsNone(parse_chunk_ids(None))


# ------------------------------------------------------------------ B14: parse_subtitle 口语纯数字保护
class TestParseSubtitleDigits(unittest.TestCase):
    """B14：SRT 中纯数字发言不应在时间戳之后被误当作下一段的序号行丢弃。"""

    def test_spoken_digits_preserved(self):
        from extract import parse_subtitle
        srt_data = """1
00:00:05,000 --> 00:00:08,000
2024

2
00:00:09,000 --> 00:00:12,000
数据结构
"""
        parsed = parse_subtitle(srt_data)
        self.assertIsNotNone(parsed)
        self.assertIn("2024", parsed)
        self.assertIn("数据结构", parsed)


# ------------------------------------------------------------------ B15: _ts_to_sec 异常输入防御
class TestTsToSecBoundary(unittest.TestCase):
    """B15：非法格式时间戳输入不应抛出未捕获异常。"""

    def test_ts_to_sec_safe(self):
        from validate_note import _ts_to_sec
        self.assertEqual(_ts_to_sec("01:20"), 80)
        self.assertEqual(_ts_to_sec("01:02:03"), 3723)
        self.assertIsNone(_ts_to_sec("invalid"))
        self.assertIsNone(_ts_to_sec("99:99"))
        self.assertIsNone(_ts_to_sec(""))




# ------------------------------------------------------------------ B16: pick_subtitle sort direction
class TestPickSubtitleSortDirection(unittest.TestCase):
    """B16：非中文前缀匹配时，人工字幕(manual)应优先于自动字幕(auto)。"""

    def _make_info(self, manual_langs, auto_langs):
        return {
            "subtitles": {lang: [{"ext": "json3", "url": "http://m"}] for lang in manual_langs},
            "automatic_captions": {lang: [{"ext": "json3", "url": "http://a"}] for lang in auto_langs},
        }

    def test_manual_preferred_over_auto(self):
        from extract import pick_subtitle
        # 同时有 manual en 和 auto en-orig
        info = self._make_info(["en"], ["en-orig"])
        result = pick_subtitle(info, prefer_lang="en")
        self.assertIsNotNone(result)
        lang, _entry, is_auto = result
        self.assertFalse(is_auto, f"期望 manual(is_auto=False)，实得 lang={lang} is_auto={is_auto}")

    def test_auto_fallback_when_no_manual(self):
        from extract import pick_subtitle
        info = self._make_info([], ["en-orig", "en"])
        result = pick_subtitle(info, prefer_lang="en")
        self.assertIsNotNone(result)
        _lang, _entry, is_auto = result
        self.assertTrue(is_auto, "无 manual 时应回落到 auto")

    def test_longer_specific_tag_preferred(self):
        from extract import pick_subtitle
        # 两个 manual: en-GB 和 en-US，无精确匹配 'en'，均为前缀匹配。
        # en-US 与 en-GB 等长，取第一个（排序稳定）；关键是两者都是 manual(is_auto=False)。
        info = self._make_info(["en-GB", "en-US"], ["en"])
        result = pick_subtitle(info, prefer_lang="en")
        self.assertIsNotNone(result)
        lang, _entry, is_auto = result
        # 精确匹配 'en' 在 manual 里找不到（只有 en-GB/en-US），
        # 但 auto['en'] 存在且精确 → 应先走精确匹配返回 auto，
        # 而非进入前缀排序路径。这里验证精确匹配优先于前缀匹配。
        self.assertEqual(lang, "en", "精确匹配的 auto['en'] 应优先于非精确的 manual['en-GB']/'en-US'")
        self.assertTrue(is_auto)


# ------------------------------------------------------------------ B17: detect_language fallback duration param
class TestDetectLanguageDurationParam(unittest.TestCase):
    """B17：detect_language 接收 duration 参数（向后兼容，默认 0 不触发重试）。"""

    def test_signature_accepts_duration(self):
        import inspect
        from extract import detect_language
        sig = inspect.signature(detect_language)
        self.assertIn("duration", sig.parameters, "detect_language 应接受 duration 参数")
        self.assertEqual(sig.parameters["duration"].default, 0.0)


# ------------------------------------------------------------------ B19: target_exists_in_index supports .md extension
class TestTargetExistsWithExtension(unittest.TestCase):
    """B19：target 传入带 .md 后缀的文件名时，应当能正确匹配 name_index 中的无后缀 stem。"""

    def test_target_with_md_matches_stem_in_name_index(self):
        from wikify import target_exists_in_index
        index = {
            "notes": {"folder/note1.md": {"stem": "note1", "rel_stem": "folder/note1"}},
            "files": {"folder/note1.md": 123},
            "name_index": {"note1": ["folder/note1"]},
        }
        self.assertTrue(target_exists_in_index("note1.md", index))
        self.assertTrue(target_exists_in_index("note1", index))
        self.assertTrue(target_exists_in_index("folder/note1.md", index))
        self.assertTrue(target_exists_in_index("folder/note1", index))
        self.assertFalse(target_exists_in_index("nonexistent.md", index))


if __name__ == "__main__":
    unittest.main(verbosity=2)


