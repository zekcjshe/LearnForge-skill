<div align="center">

# ⚒️ LearnForge (video2obsidian)

### **Turn Evidence into Real Learning.**

**专为硬核视频与 Obsidian 打造的 AI 深度学习与认知重构引擎。**  
不是粗暴压缩字幕流水账，而是把长视频与录播证据，重构成真正能学、能练、能沉淀的结构化知识体系。

<br>

[![Obsidian Native](https://img.shields.io/badge/Obsidian-Native%20Markdown-purple.svg)](https://obsidian.md/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## 💡 这是一个什么工具？

**LearnForge** 是一个连接长视频生态与个人知识库的知识工程引擎。

它不是把几万字字幕压缩成几百字流水账的普通总结器，而是专为**硬核技术课、大学公开课、多 P 选集与直播录播**设计的深度学习系统。通过分层证据提取与现代教学法重构，将视频中分散的信息沉淀为具备**直觉模型、讲师原声锚点、易错陷阱推演与主动自测题**的 Obsidian 原生笔记。

---

## 🎯 核心场景：你只需要对它说一句话

系统统一了“全网主动探索”与“单片深度精读”两条链路，你只需要自然表达需求：

### 场景一：主动学习 ——「我想学 XXX」
> **“我想彻底搞懂 Raft 分布式一致性算法，帮我从视频找优质证据整理进 Obsidian。”**

- **系统行为**：自动全网检索互补高赞视频，规划结构化学习清单，靶向提取多源视频中的互补章节，跨视频融合成一份成体系的全局知识笔记。

### 场景二：长视频精读 ——「帮我深入解析这个视频」
> **“帮我深度精读这个 2 小时的公开课：https://www.bilibili.com/video/BVxxxxxx”**

- **系统行为**：快速对长视频进行技术切片，剔除客套废话与口水词，提取核心推导逻辑、时序机制与避坑指南，生成自包含的单篇复习文档。

---

## 🛠️ 架构设计与工程优势

与传统的“视频转文字 + 简单 Prompt 总结”不同，LearnForge 是一个专门解决长上下文 Context 爆炸、模型幻觉以及非结构化证据重构的**确定性知识工程流水线**。

### 1. 分层 Token Funnel 架构（有效削减 80%+ 上下文开销）
针对 1~3 小时硬核音视频，放弃暴力塞入全量 Context，采用五级漏斗按需取证：
- **L0 导航级（Navigation）**：毫秒级解析视频结构（章节元数据、字幕快车道）；
- **L0.5 粗侦察（Acoustic Scout）**：面对无字幕长音视频，对时间分块仅抽取 20s 快速声学切片，嗅探信息密度；
- **L1 靶向提取（Target Chunks）**：仅对命中《学习规划》核心考点的分块拉取音频流并执行 Whisper 转录；
- **L1.5 证据脱水（Evidence Dehydration）**：确定性清洗过渡口水词，仅提炼核心定理、状态转移方程、关键伪代码与陷阱反例；
- **L2 教学综合（Synthesis）**：以最小必要证据集驱动大模型生成，彻底根除大模型长文本的 *Lost-in-the-Middle* 遗忘与上下文溢出。

### 2. 认知范型引擎（Exemplar-Driven Synthesis）
不采用“按学科死板堆模板”的做法，而是抽象出 4 大人类认知思维范式，动态生成自适应学习规划：
- **`mechanism`（机制时序型）**：状态机流转、网络协议握手、操作系统调度，侧重因果链条与时序演进；
- **`problem_solving`（算法优化型）**：动态规划递推、空间压缩、回溯剪枝，侧重状态定义与决策树推导；
- **`formal_security`（形式安全型）**：密码学证明、RSA、零知识证明、形式化验证，侧重数学严密性与威胁模型；
- **`system_architecture`（系统权衡型）**：分布式共识、存储引擎、CAP/PACELC 权衡，侧重方案 Trade-off 矩阵。

### 3. 双声道稀疏锚定与确定性防编造门禁
- **双声道架构**：AI 负责结构化、公式补全与推导；原片讲师负责保留不可替代的通俗比喻与直觉心智模型。
- **三问严选（Teaching Anchor）**：全篇强制最多仅准入 ≤3 条原话，必须满足“不可改写、尚未推导、一周可回忆”三项刚性指标。
- **Transcript 物理强比对（Quality Gate）**：配备独立的 `validate_note.py` 确定性审查程序，将笔记中的引用原话、秒级时间戳与底层转录文本执行逐词机械校验，彻底杜绝大模型“编造名师名言”。

### 4. 幂等区间保护与真实知识图谱注入
- **逆向 Vault 真实性索引**：集成 `wikify.py`，实时索引本地 Obsidian Vault。仅对真实存在的笔记建立双链，具备同名路径消歧与别名回退能力，不制造无效死链。
- **区间保护（Spans Union）**：自动解析 Markdown AST，对代码块、LaTeX 公式块、已有超链接实施保护区求并集计算，保证任意多次执行双链注入绝对幂等，不污染破坏已有内容。

### 5. 跨源互补与多 P 综合能力
支持主题驱动的多信源整合。当输入“我想学 X”时，系统基于 Coverage（知识覆盖）、Alternative（备选方案）、Comparison（横向对比）、Progression（认知进阶）四维算法，自动将多 P 视频与跨源切片重构成单一、自包含的复习终稿。

> *注：生态上优先深度适配 B 站（支持 B 站 MCP、ModelScope 免翻墙镜像路由）与 YouTube，输出无缝兼容 Obsidian 原生 Callout 语法与双链知识网络。*

---

## 🚀 极速上手

### 方式 A：作为 AI Agent 技能使用（推荐）
如果你正在使用 **Claude Code**、**Antigravity** 或 **Cline**，只需将本仓库克隆到技能路径即可直接对话使用：

```bash
git clone https://github.com/zekcjshe/LearnForge-skill.git "$HOME/.claude/skills/video2obsidian"
```

### 方式 B：零环境纯提示词体验
无需配置 Python 或显卡，直接取用仓库中的 [`core/teaching_base.md`](core/teaching_base.md)，将其作为 System Prompt 注入任意网页版 AI（Claude / DeepSeek / ChatGPT），贴入视频字幕即可获得同等品质的笔记。

### 方式 C：本地 CLI 开发者模式
```bash
git clone https://github.com/zekcjshe/LearnForge-skill.git
cd LearnForge-skill
pip install -r requirements.txt
```

常用功能接口：
```bash
# ① 快速查看音视频分块技术指纹索引
python extract.py "https://www.bilibili.com/video/BV1..." --chunk-index

# ② 仅提取核心切片的关键证据
python extract.py "https://www.bilibili.com/video/BV1..." --chunks 1,3 --evidence -o evidence.json

# ③ 自动为 Markdown 安全注入本地 Vault 已有双链
python wikify.py all --vault "D:/MyVault" --terms terms.json --input draft.md --output final.md

# ④ 运行确定性防幻觉门禁（校验时间戳、原话真实性与自测题闭环）
python validate_note.py final.md --vault "D:/MyVault"
```

---

## 📄 开源协议

本项目采用 [MIT 许可证](LICENSE) 开源。欢迎 Star、提交 Issue 与 PR，一起打造更懂学习者的知识锻造工具！
