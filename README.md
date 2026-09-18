<div align="center">

# ⚒️ LearnForge (video2obsidian)

### **Turn Evidence into Real Learning.**

**专为硬核技术与考研专业课打造的 AI 视频知识重构引擎。**  
将长视频、公开课与直播录播中的分散证据，沉淀为真正能学懂、能做题、能背诵的 Obsidian 体系笔记。

<br>

[![Obsidian Native](https://img.shields.io/badge/Obsidian-Native%20Markdown-purple.svg)](https://obsidian.md/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## 🎯 面向人群与解决的问题

**面向**：计算机考研（408）、高校专业课、算法刷题以及深入钻研硬核技术栈的学习者。

**解决的痛点**：
- **视频太长看不完**：1~2 小时的公开课或大课录播，有效信息密度低，边看边记笔记耗时极长；
- **看完依然不会做题**：缺乏系统的思维模型与状态演进推导，合上视频依然分不清相似概念；
- **容易踩坑掉入盲区**：视频中名师强调的易错细节与解题陷阱，往往在普通摘要中被全部洗掉；
- **知识孤立不成体系**：零散的笔记无法与已有的个人知识库自然关联。

LearnForge 不是简单的“字幕文本压缩器”，而是以**教学法五项铁律**为骨架，直接从视频音轨和字幕中提取核心证据、名师比喻与反例陷阱，重构成可自测、可复习的闭环知识对象。

---

## 💡 核心使用场景

你只需要在对话中自然表达需求：

### 场景一：主动探索 ——「我想学 XXX」
> **“我想彻底搞懂 Raft 分布式一致性算法，帮我在 B 站找优质视频整理进 Obsidian。”**

系统自动在全网检索高赞互补教程，规划知识清单，靶向提取各视频中的核心章节，跨视频融合成一份结构完整的全局知识笔记。

### 场景二：长视频精读 ——「帮我深入解析这个视频」
> **“帮我深度精读这个 2 小时的公开课：https://www.bilibili.com/video/BVxxxxxx”**

系统对长视频进行分块切片，剔除客套废话与口水词，提取核心推导逻辑、算法时序与避坑指南，生成自包含的单篇复习文档。

---

## 📝 最终生成的笔记结构

生成的笔记直接适配 **Obsidian 原生语法**，严格围绕认知路径展开：

1. 🎯 **通关目标**：明确学完本篇必须亲手解出的问题或推导出的状态机；
2. 💡 **直觉模型**：生活类比与技术实体双重锚定，击穿抽象概念卡点；
3. 🎙️ **讲师原声锚点**：全篇严选 ≤3 条名师最通透的神级比喻，附精确到秒的时间戳直达原片；
4. ⚠️ **陷阱实验室**：专门剖析考研与面试中最容易踩的坑、误区反例与正确机制推导；
5. ❓ **闭环主动自测**：内置带折叠解析的主动回忆自测题（Active Recall），合上电脑也能检验掌握程度。

---

## 🚀 极速上手

### 方式 A：作为 AI Agent 技能使用（推荐）
适用于 **Claude Code**、**Antigravity** 或 **Cline** 等智能体环境：

```bash
git clone https://github.com/zekcjshe/LearnForge-skill.git "$HOME/.claude/skills/video2obsidian"
```
挂载后，直接在聊天框发送 B 站链接或学习目标即可。

### 方式 B：零环境纯提示词体验
无需配置 Python 或显卡：
1. 打开 [`core/teaching_base.md`](core/teaching_base.md) 复制其中的教学规范；
2. 粘贴至任意网页版大模型（Claude / DeepSeek / ChatGPT）作为 System Prompt；
3. 贴入视频字幕或课程文本，即可生成同等规范的结构化笔记。

### 方式 C：本地 CLI 引擎运行
适用于需要本地自动化下载音频、离线转录与双链注入的场景：

```bash
git clone https://github.com/zekcjshe/LearnForge-skill.git
cd LearnForge-skill
pip install -r requirements.txt
```

常用接口：
```bash
# ① 快速查看视频分块指纹（毫秒级）
python extract.py "https://www.bilibili.com/video/BV1..." --chunk-index

# ② 仅提取核心切片证据并过滤废话
python extract.py "https://www.bilibili.com/video/BV1..." --chunks 1,3 --evidence -o evidence.json

# ③ 将生成好的笔记安全注入 Obsidian 本地 Vault（自动建立真实双链）
python wikify.py all --vault "D:/MyVault" --terms terms.json --input draft.md --output final.md
```

> [!TIP]
> - **优先复用字幕**：带字幕的视频无需运行语音识别模型，数秒即可提取。
> - **CPU 轻量运行**：内置 Faster-Whisper 基于 CTranslate2，轻薄本 CPU 亦可流畅离线转录，无需配置独立显卡。

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

### 4. 幂等区间保护与 Obsidian 知识网络
- **逆向 Vault 索引**：仅对本地已有的真实笔记建立 `[[双链]]`，支持同名消歧；
- **区间保护并集算法**：保护代码块、LaTeX 公式与已有链接，多次运行严格保持幂等。
</details>

---

## 📄 开源协议

本项目采用 [MIT 许可证](LICENSE) 开源。欢迎 Star、提交 Issue 与 PR，一起打造更懂学习者的知识锻造工具！
