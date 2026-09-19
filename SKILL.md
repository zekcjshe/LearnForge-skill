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
- **全篇硬上限 ≤ 6 条**（允许 0 条，宁缺毋滥；8 模块的常规产出是 2~4 条）；
- **字数 ≤ 100 字**，且单条仍须是**能一口气念完的一句短摘录**，禁止把整段讲稿搬进来；
- **格式统一规范**：
  ```markdown
  > [!quote] 🎙️ 原片教学锚点（UP主名）
  > "<短摘录，≤100 字>"
  > —— [mm:ss - mm:ss]
  ```
- **旁路生成审计资产**：按 `anchor_audit.schema.json` 约束旁路生成 `anchor_audit.json`（可通过 `python validate_note.py <note> --generate-audit <video_id>` 自动导出骨架模板，不进入最终 Markdown，用于工程回归与审计）。

### 3. 锚点真实性与高质量转化铁律（双轨溯源，杜绝碎句废话）
引文层在万字笔记中占比天然很低（上限 6 条 × 100 字 = 600 字的绝对天花板）。锚点必须兼顾**高教学信息密度（人话、易懂、无流水账）**与**真实可信溯源（杜绝凭空捏造）**。

- **核心规范：杜绝半截碎句，补充上下文，精炼为自包含、独立完整、语义清晰的一句人话**：
  - **严禁半句话/断头句**：禁止截取讲师从句中的半截短语（如缺少主语或谓语的单边小句）；单条引文必须具备**完整的逻辑主谓宾结构**或**完整的因果/对比判断**。
  - **主动补充必要上下文**：若原话散落在多句或上下文暗示中，允许结合该时间窗口（±25s 内）的前后文信息，融合成一句语义自包含的完整话，让读者脱离原片也能一眼看懂底层逻辑。
  - **字数弹性与上限**：在 **≤ 100 字**上限内，充分利用空间表达完整教学思想（常规推荐 30~70 字），切忌为了凑字数刻意切短。
- **坚决拒绝口水话与 ASR 音译乱码**：
  严禁直接把转录产生的碎碎念、结巴倒装或严重音译错字（如*“五二比侧”、“循环左一”、“多多了一个什么多了一个分组”、“把第一轮搞清楚就OK了”*）生搬硬套进笔记。
- **允许且提倡高质量人话精炼**：
  讲师原话口水过多时，必须在**保留原句核心术语、教学逻辑与经典比喻**的前提下，剔除结巴废话，进行专业化人话精炼，让学习者能真正看懂。
- **门禁二重双轨校验机制（Dual-Track Verification）**：
  `validate_note.py` 会自动执行双轨验证，满足任意一轨即判定为真锚点：
  1. **字面对齐轨**：原话本身通顺无废话，直接与原始字幕字面匹配（忽略标点与常见同音正字）。
  2. **时间窗口骨架语义轨**：原话口水过多经人话精炼后的引文，系统定位其 `[mm:ss - mm:ss]` 时间窗口原片字幕，计算 2-gram 字符骨架召回率（Recall ≥ 55% 即判定合格）。
  既杜绝脱离上下文凭空捏造（跨时段或无中生有将被当场拦截），又彻底解放引文表达质量。
- **必须带真实时间戳区间**，且与字幕中该句的实际位置一致。严禁使用 `[00:00 - 30:00]` 这类跨度极大的占位时间戳。
- **署名必须与真实信源一致**：UP 主名须与 frontmatter `sources[].author` 对应。
- **[强制] 质量门禁必须传 `--archive`**：
  ```bash
  python "<skills-dir>/video2obsidian/validate_note.py" "note.md" --vault "<vault-dir>" --archive "transcripts/<video>_archive.json"
  ```

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
   - **优先路由**：环境已配置 `@xzxzzx/bilibili-mcp` 或已挂载 `bili_helper.py` 时，直接调用 MCP 工具（`search_bilibili_videos`、`search_bilibili_creators`、`get_video_transcript`、`get_video_metadata`）检索高赞/指定 UP 主视频并秒级提取原片转录文本；
   - **降级路径（无 bilibili MCP 时）**：若当前环境未配置 bilibili MCP，Agent 自动提示用户提供 1~2 个相关 B 站/视频 URL，或使用内置 Web 搜索锁定信源；
   - 通过 `extract.py <url> --chunk-index` 或 `get_video_transcript` 查看技术指纹，仅对命中 `must_cover` 考点的章节提取 L1.5 证据。
3. **横向综合重构 (Learning Launchpad)**：
   - 提取 Teaching Anchor 候选，执行 Q1/Q2/Q3 淘汰并产出 `anchor_audit.json`；
   - 遵循六段式 Learning Launchpad 结构编写综合主题笔记。
4. **归档闭环**：执行 `wikify.py all --vault <vault>` 注入与 `validate_note.py --vault <vault> --archive <archive>` 质量门禁，确保满分入库。

---

## 🧭 用户专属工作流习惯与作业规范 (User Workflow & Preferences)

针对当前知识库（网络空间安全 893 考研 / 密码学体系），Agent 必须默认遵循以下实战工作流习惯：

1. **核心权威信源锚定**：
   - 理论、数学推导与大题考点：优先锁定**西电杨波教授**公开课；
   - 直觉模型、机制细节与工程漏洞（如 PS3 惨案）：协同使用 **UP 主「可厉害的土豆」**。
2. **教学锚点（Teaching Anchor）创作习惯**：
   - **全篇上限 6 条，单条最长 100 字**（黄金区间 30~70 字）；
   - **坚决杜绝断头句**：必须是一句自包含、语义清晰、独立完整的人话（具备完整主谓宾或逻辑判断）；
   - **主动融合上下文**：结合时间切片（±25s）前后文语义提炼精华，杜绝讲师结巴碎碎念与 ASR 乱码，且绝不为了迁就门禁降低文字质量。
3. **章节推进标准作业节拍 (Standard Cadence)**：
   - **Step 1 字幕资产固化**：先通过 Bilibili MCP 抓取全章原片字幕，合并生成 `chX_all_transcripts.json`；
   - **Step 2 教学重构与锚点精炼**：编写各分节 Launchpad 笔记，注入高质量完整句锚点；
   - **Step 3 确定性回归闭环**：编写并运行自动化测试脚本 `check_chX.py`，必须全部达到 **100/100 PASSED**；
   - **Step 4 资产版本控制与推送**：里程碑完成后，响应用户「推送」指令，规范执行 Git commit 与 push。
