# 学习计划规范 (learning_plan_schema.md)

在启动主题学习时，系统**禁止套用僵化的学科文件**，而是根据学习目标动态分析生成一份本次学习专用的 **`Learning Plan`（自适应学习计划）**。

---

## 动态 Learning Plan 结构规范 (YAML 结构)

每次规划时，AI 必须首先在内心或思考链中完成如下自适应规划：

```yaml
topic: "主题名称（如：TCP 拥塞控制）"
primary_exemplar: "mechanism"                  # 主轴范例 [mechanism | problem_solving | formal_security | system_architecture]
secondary_exemplars:
  - "system_architecture"                      # 辅轴范例（嵌入式融合，非平行堆叠）
integration_strategy:
  type: "embedded"

# 必掌握核心清单（4~6项，后续驱动视频检索与覆盖度审计）
must_cover:
  - "能力点 1：拥塞控制 vs 流量控制本质区别"
  - "能力点 2：慢开始 (Slow Start) 指数增长机制"
  - "能力点 3：拥塞避免 (AIMD 加法增大乘法减小)"
  - "能力点 4：快重传 (Fast Retransmit) 与 3 个重复 ACK"
  - "能力点 5：快恢复 (Fast Recovery) 与 Tahoe / Reno 状态机对比"

# 证据优先级（指导 L0/L0.5 关键词匹配与切片选择）
preferred_evidence:
  - "状态机时序图"
  - "cwnd 演变曲线"
  - "Wireshark 真实抓包"

# 明确规避（防止引入冗余 Token 废话）
avoid:
  - "冗长历史八卦"
  - "纯文本复读 RFC"
  - "无关环境搭建"
```

---

## 认知模式 (Cognitive Patterns) 速查表

| 模式 | 适用场景 | 核心骨架 | 参考 Exemplar |
|---|---|---|---|
| **`mechanism` (机制/协议型)** | 网络协议、操作系统调度、并发状态机、生命周期 | 报文/实体格式 → 状态演变时序 → 极端异常/断点推演 → 抓包验证与面试陷阱 | `profiles/exemplars/mechanism.md` |
| **`problem_solving` (算法/优化型)** | 动态规划、图论搜索、空间优化、贪心分治 | 场景痛点 → ≤30行暴力脚手架 → 重叠状态展开 → 方程与逐行优化 → 越界实验室 | `profiles/exemplars/problem_solving.md` |
| **`formal_security` (安全/形式证明型)** | 密码学算法 (RSA/ECC)、零知识证明、安全协议 | 威胁模型 → 形式化安全目标 → 数学基石手工算术树 → 典型攻击向量与工程缺陷 | `profiles/exemplars/formal_security.md` |
| **`system_architecture` (系统架构/权衡型)** | 数据库存储引擎、分布式一致性、系统方案横向对比 | 业务瓶颈 → 经典架构缺陷 → 异构方案横向对比矩阵 (Trade-off) → 工业级落地选型 | `profiles/exemplars/system_architecture.md` |
