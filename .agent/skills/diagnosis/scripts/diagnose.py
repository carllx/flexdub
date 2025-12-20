"""
故障诊断模块

从 agent_manual.md 的故障排除章节提取的诊断逻辑。
提供错误解析和修复建议功能。
"""

import json
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Any


@dataclass
class DiagnosisResult:
    """诊断结果"""
    error_type: str
    cause: str
    possible_reasons: List[str]
    fix_steps: List[str]
    severity: str  # "critical", "warning", "info"
    auto_fixable: bool


# 错误模式匹配规则
ERROR_PATTERNS = {
    r"TTS synthesis failed": "tts_failed",
    r"edge-tts.*error": "tts_failed",
    r"NetworkError": "tts_failed",
    r"\|delta_ms\| > 180": "sync_drift",
    r"sync.*drift": "sync_drift",
    r"text mutated": "text_mutated",
    r"RuntimeError.*text": "text_mutated",
    r"ALL PASSED = False": "qa_failed",
    r"QA.*failed": "qa_failed",
    r"ffmpeg.*error": "ffmpeg_error",
    r"negative pts": "ffmpeg_error",
    r"ratio < 0\.3": "mode_b_ratio",
    r"ratio > 3\.0": "mode_b_ratio",
    r"stretch ratio": "mode_b_ratio",
}

# 诊断知识库
DIAGNOSIS_DB: Dict[str, Dict[str, Any]] = {
    "tts_failed": {
        "cause": "TTS 合成失败",
        "possible_reasons": [
            "网络连接问题",
            "Edge TTS 服务不可用",
            "文本包含不支持的字符",
            "请求频率过高被限流",
        ],
        "fix_steps": [
            "检查网络连接",
            "等待几秒后重试",
            "检查文本是否包含特殊字符或 emoji",
            "减少并发数 (--jobs 1)",
        ],
        "severity": "critical",
        "auto_fixable": False,
    },
    "sync_drift": {
        "cause": "同步偏差过大",
        "possible_reasons": [
            "使用了错误的字幕文件（原始 SRT 而非 rebalance.srt）",
            "rebalance 参数不合适",
            "高密度片段（CPM > 300）处理不当",
            "TTS 语速与预期不符",
        ],
        "fix_steps": [
            "确认使用 rebalance.srt 而非原始 SRT",
            "调整 --target-cpm 160 --max-shift 3000",
            "对高密度片段进行手动分句",
            "检查 TTS 语速设置",
        ],
        "severity": "warning",
        "auto_fixable": True,
    },
    "text_mutated": {
        "cause": "文本不可变原则违规",
        "possible_reasons": [
            "在 Script 阶段（rebalance/merge）尝试修改文本内容",
        ],
        "fix_steps": [
            "文本修改必须在 LLM 阶段完成",
            "使用 rewrite 命令进行文本清理",
            "完成文本修改后再执行 rebalance 或 merge",
        ],
        "severity": "critical",
        "auto_fixable": False,
    },
    "qa_failed": {
        "cause": "QA 检查未通过",
        "possible_reasons": [
            "说话人标签覆盖率 < 100%",
            "片段字符数超过 250",
            "片段时长超过 15 秒",
            "voice_map.json 格式错误或缺少 DEFAULT",
        ],
        "fix_steps": [
            "补充缺失的 [Speaker:Name] 标签",
            "在逗号、分号或句号处分片",
            "调整时间轴或拆分长片段",
            "修正 voice_map.json 格式，确保包含 DEFAULT 键",
        ],
        "severity": "warning",
        "auto_fixable": True,
    },
    "ffmpeg_error": {
        "cause": "FFmpeg 处理失败",
        "possible_reasons": [
            "视频包含负 PTS 时间戳",
            "视频编码格式不支持",
            "音频采样率不匹配",
        ],
        "fix_steps": [
            "添加 --robust-ts 参数",
            "转换视频格式为 H.264/AAC",
            "指定 --ar 48000 统一采样率",
        ],
        "severity": "critical",
        "auto_fixable": True,
    },
    "mode_b_ratio": {
        "cause": "Mode B 拉伸比例异常",
        "possible_reasons": [
            "字幕分片过度合并，单片段过长",
            "TTS 生成的音频时长与预期差异过大",
        ],
        "fix_steps": [
            "Mode B 需要超细粒度分片（每句独立）",
            "确保片段数量为原始的 80%-120%",
            "检查是否有超长片段需要拆分",
        ],
        "severity": "warning",
        "auto_fixable": True,
    },
}


def detect_error_type(error_message: str) -> Optional[str]:
    """
    从错误消息中检测错误类型
    
    Args:
        error_message: 错误消息文本
        
    Returns:
        错误类型字符串，如果无法识别则返回 None
    """
    for pattern, error_type in ERROR_PATTERNS.items():
        if re.search(pattern, error_message, re.IGNORECASE):
            return error_type
    return None


def diagnose(
    error_type: Optional[str] = None,
    error_message: str = "",
    context: Optional[Dict[str, Any]] = None
) -> DiagnosisResult:
    """
    诊断错误并提供修复建议
    
    Args:
        error_type: 错误类型（可选，如果不提供则从 error_message 推断）
        error_message: 错误消息
        context: 上下文信息
        
    Returns:
        DiagnosisResult 包含诊断结果和修复建议
    """
    # 如果没有提供错误类型，尝试从消息中检测
    if not error_type:
        error_type = detect_error_type(error_message)
    
    # 如果仍然无法确定，返回通用诊断
    if not error_type or error_type not in DIAGNOSIS_DB:
        return DiagnosisResult(
            error_type=error_type or "unknown",
            cause="未知错误",
            possible_reasons=["无法确定具体原因"],
            fix_steps=[
                "检查完整的错误日志",
                "确认输入文件格式正确",
                "尝试使用默认参数重新执行",
            ],
            severity="info",
            auto_fixable=False,
        )
    
    # 获取诊断信息
    info = DIAGNOSIS_DB[error_type]
    
    return DiagnosisResult(
        error_type=error_type,
        cause=info["cause"],
        possible_reasons=info["possible_reasons"],
        fix_steps=info["fix_steps"],
        severity=info["severity"],
        auto_fixable=info["auto_fixable"],
    )


def parse_error_report(report_path: str) -> List[DiagnosisResult]:
    """
    解析错误报告文件并返回诊断结果列表
    
    Args:
        report_path: 错误报告 JSON 文件路径
        
    Returns:
        诊断结果列表
    """
    if not os.path.exists(report_path):
        return [diagnose(error_message=f"Report file not found: {report_path}")]
    
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        return [diagnose(error_message=f"Failed to parse report: {e}")]
    
    results = []
    
    # 处理报告中的错误
    errors = report.get("errors", [])
    if isinstance(errors, list):
        for error in errors:
            if isinstance(error, dict):
                result = diagnose(
                    error_type=error.get("type"),
                    error_message=error.get("message", ""),
                    context=error.get("context"),
                )
                results.append(result)
            elif isinstance(error, str):
                result = diagnose(error_message=error)
                results.append(result)
    
    # 如果没有找到错误，检查是否有失败状态
    if not results and report.get("status") == "failed":
        result = diagnose(error_message=report.get("message", "Unknown failure"))
        results.append(result)
    
    return results if results else [diagnose(error_message="No errors found in report")]


def format_diagnosis(result: DiagnosisResult) -> str:
    """
    格式化诊断结果为人类可读的文本
    
    Args:
        result: 诊断结果
        
    Returns:
        格式化的文本
    """
    lines = [
        f"## 错误诊断: {result.error_type}",
        f"",
        f"**原因**: {result.cause}",
        f"**严重程度**: {result.severity}",
        f"**可自动修复**: {'是' if result.auto_fixable else '否'}",
        f"",
        f"### 可能的原因",
    ]
    
    for reason in result.possible_reasons:
        lines.append(f"- {reason}")
    
    lines.append("")
    lines.append("### 修复步骤")
    
    for i, step in enumerate(result.fix_steps, 1):
        lines.append(f"{i}. {step}")
    
    return "\n".join(lines)
