<div align="center">

# ⚒️ LearnForge (video2obsidian)

### **Turn Evidence into Real Learning.**

**专为 B 站硬核视频与 Obsidian 知识库打造的 AI 深度学习与认知重构引擎。**  
不是粗暴压缩字幕，而是把长视频与直播证据，重构成真正能学、能练、能沉淀的知识体系。

<br>

[![Obsidian Native](https://img.shields.io/badge/Obsidian-Native%20Markdown-purple.svg)](https://obsidian.md/)
[![Bilibili First](https://img.shields.io/badge/Bilibili-First%20Learning-fb7299.svg)](#-核心优势为什么它特别适合-b-站与-obsidian-)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## 💡 这是一个什么工具？

**LearnForge** 是一个连接 **B 站长视频生态** 与 **Obsidian 个人第二大脑** 的知识工程工具。

它不是把几万字字幕压缩成几百字流水账的普通总结器，而是专为 **B 站硬核技术课、大学公开课、多 P 选集与直播录播** 设计的深度学习助手。它通过分层证据提取与现代教学法重构，将视频中分散的信息提炼为具备**直觉模型、讲师原声锚点、易错陷阱推演与主动自测题**的 Obsidian 原生笔记。

---

## 🎯 核心场景：你只需要对它说一句话

系统打通了“全网主动探索”与“单片深度精读”两条链路，你只需要自然表达需求：

### 场景一：主动学习 ——「我想学 XXX」
> **“我想彻底搞懂 Raft 分布式一致性算法，帮我在 B 站找优质视频整理进 Obsidian。”**

- **系统行为**：自动在 B 站全网检索互补高赞视频，规划结构化学习清单，靶向提取多源视频中的互补章节，跨视频融合成一份成体系的全局知识笔记。

### 场景二：长视频精读 ——「帮我深度解析这个视频」
> **“帮我深度精读这个 2 小时的公开课：https://www.bilibili.com/video/BVxxxxxx”**

- **系统行为**：快速对长视频进行技术切片，剔除客套废话与口水词，提取核心推导逻辑、时序机制与避坑指南，生成自包含的单篇复习文档。

---

## ⚡ 核心优势：为什么它特别适合 B 站与 Obsidian？

市面上的视频总结工具，面对动辄 1~3 小时的长视频和直播录播时，通常只有两种结果：**要么直接超出 Token 限制报错，要么花费极高且输出泛泛而谈的废话**。

LearnForge 针对 B 站生态与本地知识管理做了底层工程优化：

### 1. 专为 B 站优化：分层 Token 漏斗（节省 80%+ 算力与费用）
- **B 站字幕快车道（秒级响应）**：优先检测并拉取 B 站官方及 AI 字幕，毫秒级就位，零显存消耗；
- **分块粗侦察（Scout 机制）**：对无字幕的超长视频或直播录播，不进行盲目全量转录，而是按时间分块、每块仅采样 20 秒音频指纹进行技术密度探测；
- **靶向精转录**：仅对命中核心知识点的切片调用本地 Faster-Whisper 进行离线转录，从根源上斩断 80% 以上的无用音频转录与模型上下文消耗；
- **国内高速模型路由**：默认优先从 ModelScope 镜像拉取模型，阿里公共 DNS 钉扎真实 IP 抵抗代理劫持，普通轻薄本 CPU 即可快速运行。

### 2. 拒绝 AI 洗稿，保留讲师神髓（Teaching Anchor）
- 大模型极易把名师在课堂上灵光一闪的“神级比喻”洗成枯燥的书面术语；
- LearnForge 内置严苛的筛选机制，全篇**强制最多仅保留 ≤3 条最精辟的讲师原话**，并附带精确到秒的时间戳。既保持正文的高浓度结构化，又锁死最容易记住的心智模型。

### 3. 深度融入 Obsidian 知识图谱
- **原生格式适配**：采用 Obsidian 经典的 `[!tip]` 直觉、`[!danger]` 陷阱、`[!question]` 自测等 Callout 语法，排版清晰美观；
- **真实双链校验**：自动扫描并索引你本地已有的 Obsidian Vault，仅对**真实存在**的笔记词条生成 `[[双链]]`，并支持同名消歧与幂等更新，让新笔记自然嵌入你的知识网络。

### 4. 主动闭环：能学、能测、能回忆
- 每份笔记均配备学习通关目标、常见误区与易错陷阱推演；
- 内置带折叠答案的主动自测题（Active Recall），合上电脑也能检验自己是否真正掌握。

---

## 🚀 极速上手

### 方式 A：作为 AI Agent 技能使用（推荐）
如果你正在使用 **Claude Code**、**Antigravity** 或 **Cline**，只需将本仓库克隆到技能路径即可直接对话使用：

```bash
git clone https://github.com/zekcjshe/LearnForge-skill.git "$HOME/.claude/skills/video2obsidian"
```

### 方式 B：零环境纯提示词体验
无需配置 Python 或显卡，直接取用仓库中的 [`core/teaching_base.md`](core/teaching_base.md)，将其作为 System Prompt 注入任意网页版 AI（Claude / DeepSeek / ChatGPT），贴入 B 站字幕即可获得同等品质的笔记。

### 方式 C：本地 CLI 开发者模式
```bash
git clone https://github.com/zekcjshe/LearnForge-skill.git
cd LearnForge-skill
pip install -r requirements.txt
```

常用功能接口：
```bash
# ① 快速查看 B 站视频分块技术指纹索引
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
