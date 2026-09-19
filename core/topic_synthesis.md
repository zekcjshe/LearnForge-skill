# 横向主题学习系统规范 (topic_synthesis.md)

## 核心定位：从「视频转录」到「主题综合」
单视频笔记往往受限于单一讲师的视角、风格与盲区，容易产生片面认知。
**横向主题学习系统（Topic Synthesis）** 的核心目标是：
围绕一个**技术主题**（如 `[[TCP 拥塞控制]]`、`[[0-1 背包问题]]`、`[[RSA 签名]]`），将视频降级为“证据材料”，通过“自适应学习规划 (Learning Plan)”、“缺口驱动检索”与“五级 Token 漏斗”，最终沉淀为一篇**权威、完整、自包含的主题知识对象**。

---

## 核心执行流程：从学习目标到知识对象

```text
用户提出主题学习需求（如 "我要搞懂 TCP 三次握手为什么不是两次"）
               ↓
1. 自适应学习规划 (Learning Plan)
   - 确定认知模式：mechanism (机制/协议时序型)
   - 生成 4~6 项必掌握清单 (must_cover: 初始状态、两次握手的历史死锁、双向信道确认)
   - 指定所需证据类型 (preferred_evidence: 报文时序、异常延迟场景、抓包)
               ↓
2. 缺口驱动视频探路 (Search Provider: Bilibili-first, 可扩展 YouTube/Web)
   - 精选 2 个互补高赞视频（视频 A 偏原理，视频 B 偏实操抓包）
               ↓
3. 分层 Token 极简漏斗提取证据：
   - 运行 `extract.py <url> --chunk-index` 建立 L0/L0-B 技术特征导航
   - 仅对匹配 `must_cover` 的章节提取 L1.5 证据 (`--chunks <ids> --evidence`)
               ↓
4. 清单覆盖度审计 (Checklist Coverage Analysis)：
   ├── 4~6 项全部覆盖饱和 → 立即停止检索！
   └── 关键缺口缺失 → 定向搜索第 3 个视频仅抽对应缺口单一切片
               ↓
5. 综合重构为 Obsidian 主题核心笔记 (`[[Topic.md]]`)
               ↓
6. 幂等 Wikilinks 注入与确定性质量门禁 (validate_note.py)
```

---

## 分层 Token 极简漏斗 (Token Pyramid)

```text
原始长视频 (1~2 小时，数万 Token)
   ↓
[L0 免费导航] 视频章节 / 简介时间轴目录 / 字幕关键词 (0 额外开销，毫秒级)
   ↓ (无字幕且无章节时)
[L0-B 极速粗侦察] 每分块仅采样 20s 音频，用 tiny 模型粗转录技术指纹 (已下音频时仅需数秒)
   ↓
[L1 目标分块] 仅转录选中的 1~2 个核心 chunk 脱水 (--chunks 1,3)
   ↓
[L1.5 关键证据] 仅保留定理、公式、代码与陷阱句 (--evidence，二次压缩上下文)
   ↓
[L2 教学重构] 写入单一自包含 Learning Launchpad ([[Topic.md]])
```

---

## 四大横向融合模式

| 模式 | 触发场景 | 融合策略 |
|---|---|---|
| **1. 覆盖型 (Coverage)** | 视频 A 讲透了理论公式，缺少工程抓包；视频 B 补充了 Wireshark 抓包 | 依据 `learning_plan.must_cover` 查缺补漏，将多源证据拼装入统一骨架 |
| **2. 解释型 (Alternative)** | 核心难点（如 KMP next 数组、BGP 路由震荡）单片讲解晦涩 | 引入另一讲师更通透的生活类比或几何直观，在 `[⚠️ 教学解释]` 呈现双重视角 |
| **3. 对比型 (Comparison)** | 不同讲师对实现方案存在分歧（如递归 vs 递推，Go netpoll vs Java Netty） | 提取分歧焦点，绘制横向对比表格与权衡矩阵 (Trade-off Matrix) |
| **4. 进阶型 (Progression)** | 视频 A 面向初学者极简入门，视频 B 深入内核源码与硬件底层 | 按照“极简模型 → 状态展开 → 工业级性能优化”组织递进阶梯 |

---

## 知识库对象模型 (Vault Object Architecture)

```text
Obsidian Vault
├── Topics/ (主题核心笔记)          ← 知识库的一等公民（如 [[TCP 拥塞控制.md]]）
│    ├── 涵盖所有核心机制与完整推导
│    ├── 融合各视频的最佳解释、抓包与代码
│    └── 模块顶部以 [> 🎥 来源原片：...] 标注主干出处
└── Sources/ (来源佐证存储)         ← 支撑材料（按平台分层）
     ├── Bilibili/
     │    ├── BVxxxx_archive.json   (本地全量原始转录磁盘存档)
     │    └── BVxxxx.json           (精简切片与证据)
     └── YouTube/
          └── ...
```
