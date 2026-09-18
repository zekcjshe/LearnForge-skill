<div align="center">

# ⚒️ LearnForge (video2obsidian)

### **Turn Evidence into Real Learning.**

**专为硬核技术与专业课打造的 AI 视频知识重构引擎。**  
告别碎片化快餐总结，帮你把 B 站长视频、公开课与录播证据，沉淀为真正能学懂、能做题、能沉淀的体系笔记。

<br>

[![Obsidian Native](https://img.shields.io/badge/Obsidian-Native%20Markdown-purple.svg)](https://obsidian.md/)
[![Universal Markdown](https://img.shields.io/badge/Markdown-Universal%20Self--Contained-blue.svg)](#-安装与使用)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## 🎯 什么时候选它？

这个工具主要面向 **计算机考研（408）、大学专业课、算法刷题以及硬核技术学习者**。在以下两种时刻，它最能帮到你：

1. **当你面对一个复杂知识点，脑子里完全没有清晰框架时**：
   - 比如你想学“分布式共识”或“密码学”，打开 B 站搜出一堆视频，却根本不知道从哪下手、各概念之间是什么因果关系；
   - LearnForge 替你先搭建起从 0 到 1 的**认知阶梯（直觉模型 → 极简推导 → 机制演进 → 避坑陷阱）**，让你一眼看清整个知识全景。

2. **当你想要真正系统化掌握，而不是浅尝辄止时**：
   - 普通视频总结只会压缩出几百字流水账，合上电脑脑子里依然是一团乱麻；
   - LearnForge 深入音视频，把名师在黑板上的真实推导证据、通俗比喻与真题易错陷阱全部挖出来，沉淀为一套可自测、能做题的体系化笔记。

---

## 💡 核心使用场景

你只需要在对话中自然表达需求：

### 场景一：构建体系 ——「我想学 XXX」
> **“我想彻底搞懂 Raft 分布式一致性算法，帮我在 B 站找优质视频整理进 Obsidian。”**

- **系统自动做**：去 B 站全网检索高赞互补教程，规划知识清单，靶向提取各视频中的核心章节，跨视频融合成一份结构完整的全局知识笔记。

### 场景二：长视频吃透 ——「帮我深入解析这个视频」
> **“帮我深度精读这个 2 小时的公开课：https://www.bilibili.com/video/BVxxxxxx”**

- **系统自动做**：快速切片分析长视频，剔除客套废话与口水词，提取核心推导逻辑、算法时序与避坑指南，生成自包含的单篇复习文档。

---

## 📝 最终生成的笔记结构

生成的笔记严格围绕认知路径展开：

1. 🎯 **通关目标**：明确学完本篇必须亲手解出的问题或推导出的状态机；
2. 💡 **直觉模型**：生活类比与技术实体双重锚定，击穿抽象概念卡点；
3. 🎙️ **讲师原声锚点**：全篇严选 ≤3 条名师最通透的神级比喻，附精确到秒的时间戳直达原片；
4. ⚠️ **陷阱实验室**：专门剖析考研与面试中最容易踩的坑、误区反例与正确机制推导；
5. ❓ **闭环主动自测**：内置带折叠解析的主动回忆自测题（Active Recall），合上电脑也能检验掌握程度。

---

## 🚀 安装与使用

作为 **AI Agent 技能** 挂载使用（广泛兼容 **Claude Code**、**Antigravity**、**Cline / Roo Code**、**Cursor**、**Windsurf**、**Codex** 等各类支持命令执行或技能扩展的 AI 智能体）。

> 💡 **没有 Obsidian 能用吗？**  
> **完全可以！** 最终生成的是 **100% 标准自包含 Markdown**。在 Typora、Notion、VS Code 或任意编辑器中均可完美阅读（折叠自测题原生兼容）。如果你使用 Obsidian，则能额外享受双链与知识图谱的联动。

### 方式 1：直接把这段提示词发给你的智能体（最推荐，免开终端）

如果你正在使用任意 AI Agent，**直接复制以下内容发送给它**，智能体会自动拉取并配置就绪：

```text
请帮我安装这个 Agent Skill。

- 源地址：https://github.com/zekcjshe/LearnForge-skill.git
- Skill 名称：video2obsidian

请先阅读 SKILL.md 以及所有配套文件。
如果当前环境可以执行命令，请将包含 SKILL.md 的完整 skill 目录克隆或安装到当前智能体的 skills / 扩展技能目录（如 `$HOME/.claude/skills/video2obsidian`，或当前项目适用的技能扩展路径），保留 core/、profiles/ 等完整相对目录结构，并在对应目录下执行 `pip install -r requirements.txt` 安装必要依赖。安装完成后，请确认目标 skills 目录包含 SKILL.md 和全部配套文件。
```

### 方式 2：手动终端命令行安装
如果你习惯自己在终端操作：

```bash
# 1. 克隆至技能目录（以 Claude Code / Antigravity 为例，其他 Agent 请放入对应的技能/扩展路径）
git clone https://github.com/zekcjshe/LearnForge-skill.git "$HOME/.claude/skills/video2obsidian"

# 2. 安装底层音频提取与脱水依赖
cd "$HOME/.claude/skills/video2obsidian"
pip install -r requirements.txt
```

> [!TIP]
> - **优先复用字幕**：B 站带字幕的视频无需跑语音模型，数秒即可提取完毕。
> - **普通 CPU 即可跑**：内置 Faster-Whisper 基于 CTranslate2，轻薄本 CPU 也能流畅离线转录，完全无需独立显卡。
> - **全网检索与优雅降级**：主题学习模式优先联动 `bilibili` MCP 自动发现高赞互补视频；若未配置该 MCP，直接为 Agent 提供 1~2 个 B 站视频 URL 同样能完美执行多源综合。

> [!NOTE] 开发者本地同步提示
> 若在本地独立目录开发，可使用软链接（如 PowerShell: `New-Item -ItemType Junction -Path "$HOME\.claude\skills\video2obsidian" -Target "E:\LearnForge-skill"`）链接到 Agent 技能路径，避免副本版本脱节。

---

### 💬 开始使用：对 Agent 说一句话即可

挂载完成后，直接在 Agent 聊天框中发送你的需求，Agent 会在后台自动调度工具链跑完长视频下载、音频切片脱水、时间戳审计与笔记写入全流程：

- 🎯 **主题学习**：“我想彻底搞懂 Raft 分布式一致性算法，帮我在 B 站找优质视频整理进 Obsidian。”
- 🎥 **长视频精读**：“帮我深度精读这个公开课：https://www.bilibili.com/video/BVxxxxxx”

---

## 🛠️ 工程架构

<details>
<summary><b>展开查看架构细节</b></summary>

### 1. 分层 Token Funnel 架构
针对长视频，采用五级漏斗按需取证，削减 80%+ 上下文开销：
- **L0 导航级（Navigation）**：毫秒级解析视频章节元数据与字幕快车道；
- **L0.5 粗侦察（Acoustic Scout）**：面对无字幕长视频，各切片仅抽样 20s 快速声学指纹，探测技术密度；
- **L1 靶向提取（Target Chunks）**：仅对命中考点的分块拉取音频并执行 Whisper 转录；
- **L1.5 证据脱水（Evidence Dehydration）**：清洗口水词，仅保留定理、状态转移方程、核心代码与陷阱反例；
- **L2 教学综合（Synthesis）**：以最小必要证据集驱动大模型生成，避免长文本的遗忘与上下文溢出。

### 2. 认知范型引擎（Exemplars）
抽象出 4 大人类认知思维范式，自适应生成学习规划：
- **`mechanism`（机制时序型）**：状态机流转、网络协议握手、操作系统调度；
- **`problem_solving`（算法优化型）**：动态规划递推、空间压缩、回溯剪枝；
- **`formal_security`（形式安全型）**：密码学证明、RSA、零知识证明；
- **`system_architecture`（系统权衡型）**：分布式共识、存储引擎、方案 Trade-off。

### 3. 确定性防幻觉门禁（Quality Gate）
- **三问严选**：讲师原话必须满足“不可改写、尚未推导、一周可回忆”，全篇硬上限 ≤3 条；
- **物理强比对**：通过独立的 `validate_note.py`，将笔记中的引用原话、秒级时间戳与底层转录文本执行逐词机械校验，彻底杜绝大模型自我编造。

### 4. 幂等区间保护与知识网络
- **逆向 Vault 索引**：仅对本地已有的真实笔记建立 `[[双链]]`，支持同名消歧；
- **区间保护并集算法**：保护代码块、LaTeX 公式与已有链接，多次运行严格保持幂等。
</details>

---

## 📄 开源协议

本项目采用 [MIT 许可证](LICENSE) 开源。欢迎 Star、提交 Issue 与 PR，一起打造更懂学习者的知识锻造工具！
