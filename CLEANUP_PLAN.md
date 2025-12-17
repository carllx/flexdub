# PyVideoTrans 项目清理计划

**创建日期：** 2024-11-30  
**参考文档：** agent_manual_v2.md

---

## 📋 清理目标

根据 `agent_manual_v2.md` 的标准项目结构，清理过时、冗余或无价值的文件和目录。

---

## 🗑️ 待删除文件

### 1. 根目录过时文档（高优先级）

这些文档已被 `agent_manual_v2.md` 取代或不再需要：

| 文件 | 原因 | 操作 |
|------|------|------|
| `agent_manual.md` | 已被 v2 取代 | 删除 |
| `AGENT_MANUAL_UPDATE.md` | 临时更新记录，已合并到 v2 | 删除 |
| `agent_manual_v2_improvements.md` | 开发过程文档，已完成 | 删除 |
| `agent_manual_v2_lessons_learned.md` | 开发过程文档，已完成 | 删除 |
| `ELASTIC_MODES.md` | 已整合到 agent_manual_v2.md | 删除 |
| `EXECUTION_REPORT.md` | 临时执行报告 | 删除 |
| `IMPLEMENTATION_SUMMARY.md` | 临时实现总结 | 删除 |
| `MODE_B_CHECKLIST.md` | 已整合到 agent_manual_v2.md | 删除 |
| `OPTIMIZATION_SUMMARY.md` | 临时优化总结 | 删除 |
| `QUICK_START_ELASTIC_VIDEO.md` | 已整合到 agent_manual_v2.md | 删除 |
| `RESUME_MECHANISM_PROPOSAL.md` | 提案文档，未实现 | 删除 |
| `WORKAROUND_RESUME_TTS.md` | 临时解决方案文档 | 删除 |
| `roadmap.md` | 过时的路线图 | 删除 |

### 2. 临时脚本（中优先级）

| 文件 | 原因 | 操作 |
|------|------|------|
| `merge_and_compress.py` | 一次性脚本 | 删除 |
| `merge_mode_b_videos.sh` | 一次性脚本 | 删除 |
| `test_elastic_video.sh` | 测试脚本，已完成 | 删除 |
| `_fake.wav` | 测试用临时文件 | 删除 |

### 3. plans/ 目录（中优先级）

整个 `plans/` 目录已被 `agent_manual_v2.md` 取代：

```
plans/
├── 01_Core_Philosophy_v1.0.md      → 已整合到 agent_manual_v2.md 第1章
├── 02_Decision_Matrix_v1.0.md      → 已整合到 agent_manual_v2.md 第2章
├── 03_Semantic_First_Workflow_v1.0.md → 已整合到 agent_manual_v2.md 第3章
├── 04_Multi_Speaker_Protocol_v1.0.md  → 已整合到 agent_manual_v2.md 第4章
├── 05_Implementation_Guide_v1.0.md    → 已整合到 agent_manual_v2.md
├── 06_Troubleshooting_QA_v1.0.md      → 已整合到 agent_manual_v2.md 第8章
├── 07_Progress_Report_Template_v1.0.md → 不再需要
├── 08_Risk_Escalation_Plan_v1.0.md    → 不再需要
├── 09_Change_Log_and_References_v1.0.md → 使用 CHANGELOG.md
└── 10_Archive_and_Cleanup_Plan_v1.0.md  → 本文档取代
```

**操作：** 删除整个 `plans/` 目录

### 4. agents/ 目录（中优先级）

| 目录 | 原因 | 操作 |
|------|------|------|
| `agents/srt_timing_agent/` | 只有 `__pycache__`，无实际代码 | 删除整个目录 |

### 5. 其他临时目录（低优先级）

| 目录 | 原因 | 操作 |
|------|------|------|
| `tmp_proj/` | 空目录 | 删除 |
| `.trae/` | IDE 临时文件 | 删除 |

---

## 📁 data/ 目录清理

### data/input/ 清理

保留标准项目结构，删除临时文件：

| 项目 | 保留 | 删除 |
|------|------|------|
| `xpDWta5O3n8/` | ✅ 视频、SRT、voice_map.json、semantic_fixed.srt | `Retopology_360p_backup.mp4`（备份）, `tts_cache/`（可重建） |
| `9N4rG5qHWgk/` | ✅ 视频、SRT、voice_map.json、semantic_fixed.srt | `chunks/`（临时分段） |
| `I9IVtq3wrbs/` | ✅ 视频、原始SRT、gs.md | 多个 `.rewritten.*.srt` 中间文件 |
| `dj0uXid9oGo/` | ✅ 全部保留 | - |
| `AdxDVSS1rhg/` | ⚠️ 只有视频，无字幕 | 考虑删除或补充字幕 |

### data/output/ 清理

保留最终输出，删除中间产物：

| 项目 | 保留 | 删除 |
|------|------|------|
| `xpDWta5O3n8/` | `Retopology_mode_b.mp4`, `semantic_fixed.mode_b.srt` | 旧版本 `retopology_tutorial*.dub.mp4`, `mode_b_*.mp4` |
| `9N4rG5qHWgk/` | `final_output.mp4` | `concat_list.txt`, `audio_concat_list.txt`, `merged_audio.aac`, `sync_audit/`, `test_elastic_video/` |
| `I9IVtq3wrbs/` | 最终 `.dub.mp4` | 多个中间版本、`issues/`、`.csv`、`.log` 文件 |
| `Create_a_Children_s_Book...` | 最终 `.dub.mp4` | `dual_srt/` |
| `Maya_UV_Mapping...` | 最终 `.dub.mp4` | 中间 `.srt` 文件 |

---

## ✅ 保留文件

### 核心文档
- `README.md` - 项目说明
- `CHANGELOG.md` - 变更日志
- `agent_manual_v2.md` - 主要操作手册
- `pyproject.toml` - 项目配置
- `requirements.txt` - 依赖列表
- `.gitignore` - Git 忽略规则

### 核心代码
- `pyvideotrans/` - 主包（全部保留）
- `tests/` - 测试文件（全部保留）
- `scripts/` - 实用脚本（保留有价值的）

### 配置目录
- `.kiro/` - Kiro IDE 配置（保留）
- `.venv/` - 虚拟环境（保留）

---

## 🚀 执行命令

### 阶段 1：删除根目录过时文档

```bash
rm -f agent_manual.md
rm -f AGENT_MANUAL_UPDATE.md
rm -f agent_manual_v2_improvements.md
rm -f agent_manual_v2_lessons_learned.md
rm -f ELASTIC_MODES.md
rm -f EXECUTION_REPORT.md
rm -f IMPLEMENTATION_SUMMARY.md
rm -f MODE_B_CHECKLIST.md
rm -f OPTIMIZATION_SUMMARY.md
rm -f QUICK_START_ELASTIC_VIDEO.md
rm -f RESUME_MECHANISM_PROPOSAL.md
rm -f WORKAROUND_RESUME_TTS.md
rm -f roadmap.md
```

### 阶段 2：删除临时脚本和文件

```bash
rm -f merge_and_compress.py
rm -f merge_mode_b_videos.sh
rm -f test_elastic_video.sh
rm -f _fake.wav
```

### 阶段 3：删除过时目录

```bash
rm -rf plans/
rm -rf agents/
rm -rf tmp_proj/
rm -rf .trae/
```

### 阶段 4：清理 data/input/

```bash
# xpDWta5O3n8
rm -f "data/input/xpDWta5O3n8/Retopology_360p_backup.mp4"
rm -rf "data/input/xpDWta5O3n8/tts_cache/"

# 9N4rG5qHWgk
rm -rf "data/input/9N4rG5qHWgk/chunks/"

# I9IVtq3wrbs - 保留原始和最终，删除中间版本
rm -f "data/input/I9IVtq3wrbs/Maya Tutorial - How to Bake Normal Maps from High Poly to Low Poly.rewritten.llm.srt"
rm -f "data/input/I9IVtq3wrbs/Maya Tutorial - How to Bake Normal Maps from High Poly to Low Poly.rewritten.rebalance.bom.srt"
rm -f "data/input/I9IVtq3wrbs/Maya Tutorial - How to Bake Normal Maps from High Poly to Low Poly.rewritten.rebalance.srt"
```

### 阶段 5：清理 data/output/

```bash
# xpDWta5O3n8 - 保留最新的 Mode B 输出
rm -f "data/output/xpDWta5O3n8/retopology_tutorial.dub.mp4"
rm -f "data/output/xpDWta5O3n8/retopology_tutorial_v2.dub.mp4"
rm -f "data/output/xpDWta5O3n8/retopology_tutorial_v3.dub.mp4"
rm -f "data/output/xpDWta5O3n8/retopology_tutorial_v4.dub.mp4"
rm -f "data/output/xpDWta5O3n8/mode_b_720p.mp4"
rm -f "data/output/xpDWta5O3n8/mode_b_full.mp4"

# 9N4rG5qHWgk
rm -f "data/output/9N4rG5qHWgk/concat_list.txt"
rm -f "data/output/9N4rG5qHWgk/audio_concat_list.txt"
rm -f "data/output/9N4rG5qHWgk/merged_audio.aac"
rm -rf "data/output/9N4rG5qHWgk/sync_audit/"
rm -rf "data/output/9N4rG5qHWgk/test_elastic_video/"

# I9IVtq3wrbs
rm -rf "data/output/I9IVtq3wrbs/issues/"
rm -rf "data/output/I9IVtq3wrbs/I9IVtq3wrbs.edge.sync_audit.csv/"
rm -f "data/output/I9IVtq3wrbs/"*.csv
rm -f "data/output/I9IVtq3wrbs/"*.log
```

---

## 📊 预计效果

| 类别 | 删除前 | 删除后 |
|------|--------|--------|
| 根目录文档 | 20+ 个 | 5 个 |
| 目录数量 | 15+ 个 | 10 个 |
| data/ 临时文件 | 大量 | 仅保留最终产物 |

---

## ⚠️ 注意事项

1. **执行前备份**：建议先 `git commit` 当前状态
2. **分阶段执行**：按阶段逐步清理，每阶段后验证
3. **保留 .gitkeep**：确保空目录的 `.gitkeep` 文件保留
4. **视频文件**：大文件删除前确认不再需要

---

## 🔄 后续维护

清理完成后，建议：

1. 更新 `.gitignore` 添加：
   ```
   # 临时文件
   *.sync_diag.log
   *_backup.*
   tts_cache/
   ```

2. 在 `agent_manual_v2.md` 中添加清理指南章节

3. 定期清理 `data/output/` 中的旧版本文件
