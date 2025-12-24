"""
FlexDub MCP Server

提供 Model Context Protocol 工具接口，让 Agent 通过 call_tool 与 Python 逻辑交互。

支持的工具：
- analyze_project: 分析项目并推荐处理模式
- run_auto_dub: 执行自动配音工作流
- diagnose_error: 诊断错误并提供修复建议
- run_qa_check: 执行质量检查
"""

import json
import os
import sys
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Callable

from flexdub.core.analyzer import (
    analyze_project,
    recommend_mode,
    ProjectMetrics,
    ModeRecommendation
)
from flexdub.core.qa import run_qa_checks, QAReport


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class FlexDubMCPServer:
    """
    FlexDub MCP 服务器
    
    提供标准化的工具接口，支持 stdio 通信模式。
    """
    
    def __init__(self):
        self._tools: Dict[str, Callable] = {
            "analyze_project": self._tool_analyze_project,
            "recommend_mode": self._tool_recommend_mode,
            "run_qa_check": self._tool_run_qa_check,
            "diagnose_error": self._tool_diagnose_error,
            "list_tools": self._tool_list_tools,
        }
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """列出所有可用工具"""
        return [
            {
                "name": "analyze_project",
                "description": "分析项目目录，返回视频指标和推荐配置",
                "parameters": {
                    "project_dir": {"type": "string", "required": True, "description": "项目目录路径"},
                }
            },
            {
                "name": "recommend_mode",
                "description": "根据项目指标推荐处理模式 (A/B)",
                "parameters": {
                    "avg_cpm": {"type": "number", "required": True, "description": "平均 CPM"},
                    "max_cpm": {"type": "number", "required": True, "description": "最大 CPM"},
                    "duration_ms": {"type": "number", "required": True, "description": "视频时长(ms)"},
                }
            },
            {
                "name": "run_qa_check",
                "description": "执行 SRT 质量检查",
                "parameters": {
                    "srt_path": {"type": "string", "required": True, "description": "SRT 文件路径"},
                    "voice_map_path": {"type": "string", "required": False, "description": "voice_map.json 路径"},
                    "max_chars": {"type": "number", "required": False, "description": "最大字符数限制"},
                    "max_duration_ms": {"type": "number", "required": False, "description": "最大时长限制(ms)"},
                }
            },
            {
                "name": "diagnose_error",
                "description": "诊断错误并提供修复建议",
                "parameters": {
                    "error_type": {"type": "string", "required": True, "description": "错误类型"},
                    "error_message": {"type": "string", "required": False, "description": "错误消息"},
                    "context": {"type": "object", "required": False, "description": "上下文信息"},
                }
            },
            {
                "name": "list_tools",
                "description": "列出所有可用工具",
                "parameters": {}
            },
        ]
    
    def call_tool(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        """
        调用指定工具
        
        Args:
            name: 工具名称
            arguments: 工具参数
            
        Returns:
            ToolResult 包含执行结果或错误信息
        """
        if name not in self._tools:
            return ToolResult(
                success=False,
                error=f"Unknown tool: {name}. Available: {list(self._tools.keys())}"
            )
        
        try:
            result = self._tools[name](arguments)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    def _tool_analyze_project(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """分析项目工具"""
        project_dir = args.get("project_dir")
        if not project_dir:
            raise ValueError("project_dir is required")
        
        metrics = analyze_project(project_dir)
        recommendation = recommend_mode(metrics)
        
        return {
            "metrics": asdict(metrics),
            "recommendation": asdict(recommendation),
        }
    
    def _tool_recommend_mode(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """推荐模式工具"""
        avg_cpm = args.get("avg_cpm")
        max_cpm = args.get("max_cpm")
        duration_ms = args.get("duration_ms")
        
        if avg_cpm is None or max_cpm is None or duration_ms is None:
            raise ValueError("avg_cpm, max_cpm, duration_ms are required")
        
        # 创建临时 metrics 对象
        metrics = ProjectMetrics(
            project_dir="",
            video_path="",
            srt_path="",
            duration_ms=duration_ms,
            segment_count=0,
            avg_cpm=avg_cpm,
            max_cpm=max_cpm,
            min_cpm=0,
            detected_language="unknown",
            speaker_count=1,
            has_voice_map=False,
        )
        
        recommendation = recommend_mode(metrics)
        return asdict(recommendation)
    
    def _tool_run_qa_check(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """QA 检查工具"""
        srt_path = args.get("srt_path")
        if not srt_path:
            raise ValueError("srt_path is required")
        
        voice_map_path = args.get("voice_map_path")
        max_chars = args.get("max_chars", 250)
        max_duration_ms = args.get("max_duration_ms", 15000)
        
        report = run_qa_checks(
            srt_path=srt_path,
            voice_map_path=voice_map_path,
            max_chars=max_chars,
            max_duration_ms=max_duration_ms,
        )
        
        return asdict(report)
    
    def _tool_diagnose_error(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """错误诊断工具"""
        error_type = args.get("error_type")
        if not error_type:
            raise ValueError("error_type is required")
        
        error_message = args.get("error_message", "")
        context = args.get("context", {})
        
        # 错误诊断知识库
        diagnosis_db = {
            "tts_failed": {
                "cause": "TTS 合成失败",
                "possible_reasons": [
                    "网络连接问题",
                    "Edge TTS 服务不可用",
                    "文本包含不支持的字符",
                ],
                "fix_steps": [
                    "检查网络连接",
                    "重试（可能是临时问题）",
                    "检查文本是否包含特殊字符",
                ],
            },
            "sync_drift": {
                "cause": "同步偏差过大 (|delta_ms| > 180ms)",
                "possible_reasons": [
                    "使用了错误的字幕文件",
                    "rebalance 参数不合适",
                    "高密度片段处理不当",
                ],
                "fix_steps": [
                    "确认使用 rebalance.srt 而非原始 SRT",
                    "调整 --target-cpm 和 --max-shift 参数",
                    "对高密度片段进行手动分句",
                ],
            },
            "text_mutated": {
                "cause": "文本不可变违规",
                "possible_reasons": [
                    "在 Script 阶段尝试修改文本内容",
                ],
                "fix_steps": [
                    "文本修改必须在 LLM 阶段完成",
                    "使用 rewrite 命令进行文本清理",
                    "然后再执行 rebalance 或 merge",
                ],
            },
            "qa_failed": {
                "cause": "QA 检查失败",
                "possible_reasons": [
                    "说话人标签覆盖率不足",
                    "片段字符数超限",
                    "片段时长超限",
                    "voice_map.json 格式错误",
                ],
                "fix_steps": [
                    "补充 [Speaker:Name] 标签",
                    "在逗号/分号处分片",
                    "调整时间轴或分片",
                    "修正 JSON 格式，添加 DEFAULT",
                ],
            },
            "ffmpeg_error": {
                "cause": "FFmpeg 处理失败",
                "possible_reasons": [
                    "负 PTS 时间戳",
                    "编码不支持",
                ],
                "fix_steps": [
                    "使用 --robust-ts 参数",
                    "检查视频格式是否支持",
                ],
            },
            "mode_b_ratio": {
                "cause": "Mode B 拉伸比例异常 (ratio < 0.3 或 > 3.0)",
                "possible_reasons": [
                    "字幕分片过度合并",
                ],
                "fix_steps": [
                    "Mode B 需要超细粒度分片",
                    "每个句子独立成片",
                    "片段数量应为原始 80%-120%",
                ],
            },
        }
        
        # 查找匹配的诊断
        diagnosis = diagnosis_db.get(error_type, {
            "cause": f"未知错误类型: {error_type}",
            "possible_reasons": ["无法确定原因"],
            "fix_steps": ["请检查错误日志获取更多信息"],
        })
        
        return {
            "error_type": error_type,
            "error_message": error_message,
            "diagnosis": diagnosis,
            "context": context,
        }
    
    def _tool_list_tools(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """列出工具"""
        return {"tools": self.list_tools()}