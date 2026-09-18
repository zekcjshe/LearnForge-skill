<div align="center">

# ⚒️ LearnForge (video2obsidian)

### **Turn Evidence into Real Learning.**

**专为硬核知识学习打造的 AI 视频证据重构引擎。**  
帮你把 B 站 2 小时的公开课、技术大课与直播录播，锻造成真正能学懂、能做题、能背诵的 Obsidian 笔记。

<br>

[![Obsidian Native](https://img.shields.io/badge/Obsidian-Native%20Markdown-purple.svg)](https://obsidian.md/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## 🚨 为什么我不直接问 DeepSeek，而需要这个工具？

很多同学的第一反应是：*“我直接去网页端问 DeepSeek / ChatGPT 不香吗？为什么还要折腾这个？”*

看一眼下面的对比就明白了：

| 对比维度 | 直接问网页版 AI (DeepSeek / ChatGPT) | 用 LearnForge 提炼视频证据 |
|:---|:---|:---|
| **知识来源** | **空中楼阁**：输出千篇一律的教科书八股文，枯燥难背，没有真实语境。 | **名师真凭实据**：从 B 站 2 小时原声视频里，扒出名师黑板上的推演逻辑与独家口诀。 |
| **超长视频** | **无能为力**：网页版根本无法丢入 2 小时视频，更传不了几百兆音频。 | **一键代看**：替你“坐牢”听完 2 小时，自动过滤口水词，只榨取高浓度干货。 |
| **避坑与陷阱** | **只有标准答案**：不会告诉你大家最容易在哪理解错、真题怎么挖坑。 | **实战踩坑推演**：抓取讲师反复敲黑板的“翻车反例”与高频丢分细节。 |
| **真实性验证** | **容易一本正经胡说八道**：推导跳步或记错细节时，你根本看不出来。 | **秒级时间戳回溯**：核心结论直接标出 `[14:25]`，点击直达 B 站原片核验。 |
| **学后留存** | **被动阅读**：看的时候觉得懂了，合上电脑脑子一片空白。 | **闭环认知**：直觉模型 → 讲师原声 → 陷阱题 → 闭环主动自测，专为掌握而设计。 |

> **一句话大白话**：  
> 直接问 AI，得到的是死板的参考答案；  
> **LearnForge 是雇了一个助教替你看完 2 小时名师视频，把老师讲透的直觉、考点和避坑指南，整理成你能直接背的笔记。**

---

## 🎯 核心场景：你只需要对它说一句话

系统统一了“全网主动探索”与“单片深度精读”两条链路：

### 场景一：主动学习 ——「我想学 XXX」
> **“我想彻底搞懂 Raft 分布式一致性算法，帮我在 B 站找优质视频整理进 Obsidian。”**

- **系统自动做**：去 B 站全网检索互补的高赞讲解，梳理出通关大纲，提取多视频里的互补章节，合成一份结构完整的全局知识体系。

### 场景二：长视频吃透 ——「帮我深入解析这个视频」
> **“帮我深度精读这个 2 小时的公开课：https://www.bilibili.com/video/BVxxxxxx”**

- **系统自动做**：快速切片分析长视频，剔除客套废话，提取核心推导逻辑、时序机制与踩坑预警，生成单篇自包含的复习笔记。

---

## 📝 最终生成的笔记长什么样？

输出的笔记不是时间轴流水账，而是专为学习者大脑设计的 **Obsidian 原生结构**：

1. 🎯 **全篇通关目标**：明确学完这篇笔记你必须亲手解出的问题或画出的时序；
2. 💡 **直觉心智模型**：用最接地气的生活类比 + 技术实体双重锚定（如“流量控制管水桶多大，拥塞控制管整条马路堵不堵”）；
3. 🎙️ **讲师原声锚点**：全篇严选 ≤3 条名师最通透的神级比喻，附精确到秒的时间戳，保留记忆抓手；
4. ⚠️ **陷阱实验室**：专门推演大家最容易在哪踩坑、为什么会出现这个误解、正确的推导逻辑是什么；
5. ❓ **闭环主动自测**：内置折叠答案的检测题（Active Recall），合上电脑也能检验自己是否真正学会。

---

## 🚀 极速上手：我该怎么用起来？

你可以根据当前手头的环境，选择最舒服的使用方式：

### 姿势 1：作为 AI Agent 技能使用（最推荐 ⭐⭐⭐⭐⭐）
如果你在使用 **Claude Code**、**Antigravity** 或 **Cline** 等 AI 编码与研究 Agent，只需将本仓库克隆到技能目录即可：

```bash
git clone https://github.com/zekcjshe/LearnForge-skill.git "$HOME/.claude/skills/video2obsidian"
```
挂载后，你只需要在 Agent 聊天框里直接贴 B 站链接，或说一句“我想学 XXX”，Agent 就会在后台自动调用底层工具跑完整个提取与重构流程。

---

### 姿势 2：零环境纯提示词体验（手机 / 宿舍电脑今晚就能试）
> **无需安装 Python，无需显卡环境。**

1. 打开仓库里的 [`core/teaching_base.md`](core/teaching_base.md)，复制里面的核心教学规范；
2. 粘贴作为 System Prompt 输入给你常用的网页版 AI（DeepSeek / Claude / ChatGPT）；
3. 将你手头任何课程的字幕或文稿贴进去，输入：“*按上述教学规范为我重构成 Obsidian 笔记*”，立刻体验高质量的认知重构效果！

---

### 姿势 3：本地 CLI 引擎运行（适合极客与本地开发者）
如果你有 Python 环境，想在本地自动化拉取音频、离线 Whisper 识别并自动注入 Obsidian 双链：

```bash
# 1. 克隆与安装依赖
git clone https://github.com/zekcjshe/LearnForge-skill.git
cd LearnForge-skill
pip install -r requirements.txt

# 2. 常用操作指令
# 快速查看视频技术分块指纹（毫秒级）
python extract.py "https://www.bilibili.com/video/BV1..." --chunk-index

# 仅提取核心切片证据并过滤废话
python extract.py "https://www.bilibili.com/video/BV1..." --chunks 1,3 --evidence -o evidence.json

# 将生成好的笔记安全注入 Obsidian 本地 Vault（自动建立真实双链）
python wikify.py all --vault "D:/MyVault" --terms terms.json --input draft.md --output final.md
```

> [!TIP] 💡 提示
> - **带字幕视频秒级提取**：B 站带字幕的视频无需跑语音模型，3 秒即可就位，0 显存消耗。
> - **轻薄本 CPU 即可跑**：内置的 Faster-Whisper 模型基于 CTranslate2，普通 CPU 也能轻快离线转录，完全无需高配独立显卡。

---

## 🛠️ 深入工程原理（架构探秘）

<details>
<summary><b>🔍 点击展开：为什么它省 Token、不幻觉？（极客与开发者必读）</b></summary>

### 1. 分层 Token Funnel 架构（削减 80%+ 上下文开销）
针对 1~3 小时硬核音视频，放弃暴力塞入全量 Context，采用五级漏斗按需取证：
- **L0 导航级（Navigation）**：毫秒级解析视频结构（章节元数据、字幕快车道）；
- **L0.5 粗侦察（Acoustic Scout）**：面对无字幕长音视频，对时间分块仅抽取 20s 快速声学切片，嗅探技术密度；
- **L1 靶向提取（Target Chunks）**：仅对命中核心考点的分块拉取音频流并执行 Whisper 转录；
- **L1.5 证据脱水（Evidence Dehydration）**：确定性清洗过渡口水词，仅提炼核心定理、状态转移方程、关键伪代码与陷阱反例；
- **L2 教学综合（Synthesis）**：以最小必要证据集驱动大模型生成，彻底根除长文本的 *Lost-in-the-Middle* 遗忘与上下文溢出。

### 2. 认知范型引擎（Exemplar-Driven Synthesis）
不采用死板的学科模板，而是抽象出 4 大人类认知思维范式：
- **`mechanism`（机制时序型）**：状态机流转、网络协议握手、操作系统调度，侧重因果链条与时序演进；
- **`problem_solving`（算法优化型）**：动态规划递推、空间压缩、回溯剪枝，侧重状态定义与决策树推导；
- **`formal_security`（形式安全型）**：密码学证明、RSA、零知识证明，侧重数学严密性与威胁模型；
- **`system_architecture`（系统权衡型）**：分布式共识、存储引擎、CAP 权衡，侧重方案 Trade-off 矩阵。

### 3. 确定性防编造门禁（Quality Gate）
- **三问严选**：讲师原话必须满足“不可改写、尚未推导、一周可回忆”，全篇强制 ≤3 条；
- **物理强比对**：通过独立的 `validate_note.py`，将笔记中的引用原话、秒级时间戳与底层转录文本执行逐词机械比对，彻底杜绝大模型编造假口诀。

### 4. 幂等区间保护与 Obsidian 知识网络
- **逆向 Vault 真实性索引**：仅对本地 Vault 真实存在的笔记建立 `[[双链]]`，支持同名消歧；
- **区间保护并集算法**：保护代码块、LaTeX 公式与已有链接，多次运行严格保持幂等。
</details>

---

## 📄 开源协议

本项目采用 [MIT 许可证](LICENSE) 开源。欢迎 Star、提交 Issue 与 PR，一起打造更懂学习者的知识锻造工具！
