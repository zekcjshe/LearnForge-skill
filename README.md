<div align="center">

# ⚒️ LearnForge (video2obsidian)

### **Turn Evidence into Real Learning.**

**专为硬核技术与专业课打造的 AI 视频知识重构引擎。**  
告别碎片化快餐总结，帮你把 B 站长视频、公开课与录播证据，沉淀为真正能学懂、能做题、能沉淀的体系笔记。

<br>

[![Obsidian Native](https://img.shields.io/badge/Obsidian-Native%20Markdown-purple.svg)](https://obsidian.md/)
[![Universal Markdown](https://img.shields.io/badge/Markdown-Universal%20Self--Contained-blue.svg)](#-极速上手我该怎么用起来)
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

## 🚀 极速上手：我该怎么用起来？

> 💡 **没有 Obsidian 能用吗？**  
> **完全可以！** 最终生成的是 **100% 标准自包含 Markdown**。在 Typora、Notion、VS Code 或任意编辑器中均可完美阅读（折叠自测题原生兼容）。如果你使用 Obsidian，则能额外享受双链与知识图谱的联动。

你可以根据手头的条件，选择最适合的使用方式：

### 姿势 1：零环境纯提示词体验（今晚就能试）
> **适合：快速体验“认知重构”的笔记框架，无需安装任何环境与依赖。**

1. 打开仓库里的 [`core/teaching_base.md`](core/teaching_base.md) 复制其中的教学规范；
2. 粘贴至任意网页版大模型（DeepSeek / Claude / ChatGPT）作为 System Prompt；
3. 贴入你手头的课程字幕或讲义文本，让 AI 为你重构成结构化笔记。
*(注：纯提示词模式专注于输出直觉、陷阱推演与自测题；若需全自动处理 2 小时视频、秒级时间戳精准核验与知识库双链，请使用姿势 2 或 3)*

### 姿势 2：作为 AI Agent 技能使用（最省心 ⭐⭐⭐⭐⭐）
> **适合：使用 Claude Code、Antigravity 或 Cline 等智能体的学习者。**

```bash
git clone https://github.com/zekcjshe/LearnForge-skill.git "$HOME/.claude/skills/video2obsidian"
```
挂载后，直接在聊天框贴 B 站链接或说“我想学 XXX”，Agent 会在后台自动调用工具链，跑完长视频下载、音频切片脱水、时间戳审计与笔记写入全流程。

### 姿势 3：本地 CLI 引擎运行（适合开发者 / 离线批处理）
> **适合：有 Python 环境，希望本地自动化下载与脱水。**

```bash
# 1. 安装依赖
git clone https://github.com/zekcjshe/LearnForge-skill.git
cd LearnForge-skill
pip install -r requirements.txt

# 2. 常用操作指令
# 快速查看视频分块指纹（毫秒级）
python extract.py "https://www.bilibili.com/video/BV1..." --chunk-index

# 仅提取核心切片证据并过滤废话
python extract.py "https://www.bilibili.com/video/BV1..." --chunks 1,3 --evidence -o evidence.json

# 将生成好的笔记安全注入本地 Vault（自动建立真实双链）
python wikify.py all --vault "D:/MyVault" --terms terms.json --input draft.md --output final.md
```

> [!TIP]
> - **优先复用字幕**：带字幕的视频无需跑语音模型，数秒即可提取完毕。
> - **普通 CPU 即可跑**：内置 Faster-Whisper 基于 CTranslate2，轻薄本 CPU 也能流畅离线转录，完全无需独立显卡。

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
