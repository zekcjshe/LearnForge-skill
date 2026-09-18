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


if __name__ == "__main__":
    unittest.main(verbosity=2)
