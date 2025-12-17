# Parameter Standards - Single Source of Truth

本文档定义 flexdub 的**权威参数标准**，所有文档必须遵循此规范。

## 📌 核心原则

1. **代码即真相** - CLI 默认值是唯一权威来源
2. **场景优化** - 特殊场景的参数调整作为建议，不改变默认值
3. **版本同步** - 参数变更必须同步更新所有文档

---

## 🎯 默认参数（来自代码）

### 通用参数
| 参数 | 默认值 | 适用命令 | 说明 |
|------|--------|----------|------|
| `--ar` | `48000` | merge, json_merge, project_merge, sync_audit | 采样率（Hz） |
| `--target-cpm` | `180` | merge, rebalance, json_merge, project_merge | 目标 CPM |
| `--panic-cpm` | `300` | merge, rebalance, json_merge, project_merge | 恐慌阈值 CPM |
| `--max-shift` | `1000` | merge, rebalance, json_merge, project_merge | 最大边界位移（ms） |
| `--jobs` | `4` | merge, json_merge, project_merge | 并发数 |
| `--min-cpm` | `180` | audit, json_audit | 审计最小 CPM |
| `--max-cpm` | `220` | audit, json_audit | 审计最大 CPM |
| `--win-ms` | `20` | sync_audit | 波形窗口（ms） |
| `--max-chars` | `250` | rewrite | 单块最大字符数 |
| `--max-duration` | `15000` | rewrite | 单块最大时长（ms） |

### 特殊行为参数
| 参数 | 默认值 | 行为 |
|------|--------|------|
| `--no-rebalance` | `False` | 跳过再平衡阶段 |
| `--clustered` | `False` | 启用聚类合成（自动跳过 rebalance） |
| `--auto-dual-srt` | `False` | 自动生成双轨字幕 |
| `--llm-dual-srt` | `False` | 使用 LLM 生成双轨（需配置环境变量） |
| `--no-fallback` | `False` | 禁用后端回退（强制 jobs=1） |
| `--robust-ts` | `False` | 启用健壮时序参数（手动指定） |
| `--debug-sync` | `False` | 生成同步调试日志 |

---

## 🔄 自动行为（代码逻辑）

### 1. `--clustered` 模式
```python
if args.clustered or args.auto_dual_srt:
    # 自动跳过 rebalance
    # 使用 build_audio_from_srt_clustered
```

### 2. `--no-fallback` 模式
```python
if backend == "macos_say" or args.no_fallback:
    jobs = 1  # 强制串行
```

### 3. `--robust-ts` 自动检测
```python
auto_robust = detect_negative_ts(args.video_path)
mux_audio_video(..., robust_ts=(args.robust_ts or auto_robust))
```
**说明：** 即使用户不指定 `--robust-ts`，系统也会自动检测负 PTS 并启用。

### 4. `--llm-dual-srt` 回退
```python
if args.llm_dual_srt:
    try:
        d_items, a_items = llm_generate_dual_srt(items)
    except:
        # 回退到本地 semantic_restructure
        d_items = items
        a_items = semantic_restructure(items)
```

---

## 🎨 场景优化建议（不改变默认值）

### 高密度字幕场景
**触发条件：** `cpm ≥ 900` 或 `duration_ms < 800 且 chars ≥ 30`

**建议参数：**
```bash
--target-cpm 160 \
--panic-cpm 300 \
--max-shift 6000
```

**说明：** 这是**建议值**，不是默认值。用户需要根据实际情况手动调整。

### 严格 Edge 模式
**建议参数：**
```bash
--backend edge_tts \
--jobs 1 \
--no-fallback \
--clustered
```

### 常规中文配音
**使用默认值即可：**
```bash
--target-cpm 180 \
--panic-cpm 300 \
--max-shift 1000 \
--jobs 4
```

---

## 🚫 参数互斥规则

### 1. `--keep-brackets` vs `--strip-meta`
- **互斥** - 不能同时使用
- `--keep-brackets`: 保留所有括号内容
- `--strip-meta`: 移除 `[` `]` `【` `】` 括号

### 2. `--clustered` vs `--no-rebalance`
- **冗余** - `--clustered` 已自动跳过 rebalance
- 建议只使用 `--clustered`

### 3. `--llm-dual-srt` 依赖 `--auto-dual-srt`
- **依赖关系** - `--llm-dual-srt` 需要 `--auto-dual-srt` 启用
- 代码中会自动处理，但建议显式指定

---

## 📝 文档更新检查清单

当参数变更时，必须更新以下文档：

- [ ] `agent_manual.md` - Overview 部分的默认值
- [ ] `agent_manual.md` - CLI Commands 部分的参数说明
- [ ] `agent_manual.md` - Typical Workflows 中的示例命令
- [ ] `README.md` - Command Examples
- [ ] `.kiro/steering/tech.md` - Default Parameters
- [ ] `.kiro/specs/agent-orchestration-system/requirements.md` - 相关需求
- [ ] `plans/02_Decision_Matrix_v1.0.md` - 决策矩阵中的参数

---

## 🔍 验证方法

### 自动验证脚本
```bash
# 检查文档中的参数是否与代码一致
grep -r "target-cpm" agent_manual.md | grep -v "180"
grep -r "panic-cpm" agent_manual.md | grep -v "300"
grep -r "max-shift" agent_manual.md | grep -v "1000"
```

### 手动验证
1. 运行 `python -m flexdub merge --help` 查看实际默认值
2. 对比文档中的所有参数说明
3. 确保示例命令可执行

---

## 📅 版本历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v1.0 | 2024-11-30 | 初始版本，基于代码 v2.0.0 |

---

## 🔗 相关文档

- [agent_manual.md](../../agent_manual.md) - Agent 操作手册
- [requirements.md](./requirements.md) - 需求规范
- [CLI 源码](../../flexdub/cli/__main__.py) - 权威参数定义
