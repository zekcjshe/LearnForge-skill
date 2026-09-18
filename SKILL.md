---
name: video2obsidian
description: 视频知识提炼与自适应主题学习系统。支持单视频秒级脱水（字幕快车道/Whisper VAD/Token五级漏斗）与目标驱动多源横向学习（动态Learning Plan/缺口驱动检索/Learning Launchpad教学重构），输出高质量自包含 Obsidian 教学笔记，支持 Wikilinks 幂等注入、Teaching Anchor 确定性审计与质量门禁。
---

# LearnForge (video2obsidian): 视频证据提炼与自适应学习系统

根据用户指令意图，自动分流进入 **模式 A (单视频提炼)** 或 **模式 B (横向主题学习)**。
底层严格遵循 [`core/teaching_base.md`](core/teaching_base.md) 通用教学五项铁律与 [`core/provenance.md`](core/provenance.md) 来源可溯性规范。

> [!IMPORTANT] 零心智负担原则 (Zero-Config User Experience)
> 复杂性留在系统内部，简单性留给用户。用户只需表达学习目标或提供 URL，所有内部工具链调度（`extract.py`、`bilibili` MCP、`wikify.py`、`validate_note.py`）由 AI 在后台自主闭环完成，向用户仅呈现清晰的阶段里程碑与最终高质量笔记，绝不向用户转嫁底层 CLI 参数。

---

## 🎙️ Teaching Anchor 规则（稀缺性与确定性审计）

Teaching Anchor 是保留“原讲师怎么讲这个知识”的短摘录，不是“大段字幕搬运”。它和 AI 正文形成双声道：AI 负责结构化与推导，Anchor 负责保留直觉抓手。

### 1. 三问筛选法（三问全过才能进入候选排序）
- **Q1 不可替换**：把这句话改写成 AI 语言，损失了什么？（损失信息 → 淘汰；损失形象比喻/语气/记忆点 → 通过）
- **Q2 不可推导**：AI 正文已经能严格推导出来吗？（能推出 → 淘汰冗余；推不出 → 通过）
- **Q3 可记忆**：一周后学生还能记住这句话吗？（记不住 → 淘汰；能记住 → 通过）
*强制要求*：每个候选必须在 `anchor_audit.json` 中写出具体文字理由，不允许只填布尔值。

### 2. 全局稀缺性铁律
- **全篇硬上限 ≤ 3 条**（允许 0 条，宁缺毋滥，8 模块仅 1~2 条是完全正确的结果）；
- **字数 ≤ 50 字**，严格禁止连续长句；
- **格式统一规范**：
  ```markdown
  > [!quote] 🎙️ 原片教学锚点（UP主名）
  > "<短摘录，≤50 字>"
  > —— [mm:ss - mm:ss]
  ```
- **旁路生成审计资产**：按 `anchor_audit.schema.json` 约束旁路生成 `anchor_audit.json`（可通过 `python validate_note.py <note> --generate-audit <video_id>` 自动导出骨架模板，不进入最终 Markdown，用于工程回归与审计）。

---

## 🧩 Exemplar 组合规则（辅轴嵌入主轴）

```yaml
primary_exemplar: mechanism
secondary_exemplars:
  - system_architecture
integration_strategy:
  type: embedded
```
- **组合 ≠ 叠加**：严禁出现并列平行的“独立架构权衡/总结”章节；
- **判据**：权衡与考量必须作为插叙/注解，散落嵌入在主机制的每个演进步骤内部；
- **验收方式**：检查最终 Markdown 模块标题清单，出现独立“架构分析/权衡”大标题则判定失败。

---

## 模式 A：单视频提炼模式（用户提供 URL / "总结这个视频"）

1. **五级 Token 递进证据提取**：
   ```bash
   # 1. 优先提取智能导航索引（自动执行字幕快车道、内嵌章节匹配与 L0-B 极速粗侦察）
   python "<skills-dir>/video2obsidian/extract.py" "<URL>" --chunk-index
   # 2. 仅对相关分块提取 L1.5 极简证据（再压 50% 上下文）
   python "<skills-dir>/video2obsidian/extract.py" "<URL>" --chunks 1,2 --evidence --json -o "<temp-dir>/v2n.json"
   ```
2. **知识重构**：编写自包含 Learning Launchpad（Pre-test 预测试、通关目标、直觉模型、代码/机理推演、陷阱实验室、Post-test 自测、Recall Cards、Verifiable Micro-task）。
3. **知识连接与确定性质量门禁**：
   ```bash
   # 1. 术语提取 + 幂等注入（严格校验 Vault 真实存在性）
   #    必须用 all（= scan + inject 一步到位）：直接用 inject 在全新机器上会因
   #    索引不存在而 exit 2。此处使用 --weak-links none 保持正文纯净，避免在文末产生多余弱链/歧义页脚。
   python "<skills-dir>/video2obsidian/wikify.py" all --vault "<vault-dir>" --terms "terms.json" --input "note.md" --output "note_final.md" --weak-links none
   # 2. 确定性质量审计（Active Recall 检验、代码与 Mermaid 检查、Wikilink 真实性、Anchor 机械与原文溯源检查）
   python "<skills-dir>/video2obsidian/validate_note.py" "note_final.md" --vault "<vault-dir>" --archive "<archive-path>" --audit "<audit-json-path>"
   ```

---

## 模式 B：横向主题学习模式（用户提需求 "我要学 <Topic>" / "搞懂 <Topic>"）

1. **自适应学习规划 (Learning Plan)**：
   - 参考 [`core/learning_plan_schema.md`](core/learning_plan_schema.md) 与 [`profiles/exemplars/`](profiles/exemplars/) 认知范例，动态生成 `Learning Plan`：指定 `primary_exemplar` 与 `secondary_exemplars`，定义嵌入式融合策略与必掌握清单 (`must_cover`)。
2. **缺口驱动多源取证 (Bilibili-First Discovery)**：
   - **优先路由**：环境已加载 `bilibili` MCP 时，调用 MCP 工具（`bilibili-search-summary`、`bilibili-video-detail`）检索高赞互补视频；
   - **降级路径（无 bilibili MCP 时）**：若当前环境未配置 bilibili MCP，Agent 自动提示用户提供 1~2 个相关 B 站/视频 URL，或使用内置 Web 搜索（如搜索 `site:bilibili.com <Topic>`）锁定信源；
   - 通过 `extract.py <url> --chunk-index` 查看技术指纹，仅对命中 `must_cover` 考点的章节提取 L1.5 证据。
3. **横向综合重构 (Learning Launchpad)**：
   - 提取 Teaching Anchor 候选，执行 Q1/Q2/Q3 淘汰并产出 `anchor_audit.json`；
   - 遵循六段式 Learning Launchpad 结构编写综合主题笔记。
4. **归档闭环**：执行 `wikify.py all --vault <vault>` 注入与 `validate_note.py --vault <vault> --archive <archive>` 质量门禁，确保满分入库。
