"""
Workflow Orchestration Module

提供配音工作流的状态管理和步骤编排功能。
遵循 "Markdown 驱动的脚本编排" 架构。
"""

import json
import os
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Optional, List, Dict, Any

from flexdub.core.analyzer import analyze_project, recommend_mode
from flexdub.core.qa import run_qa_checks


class WorkflowStep(Enum):
    """工作流步骤"""
    INIT = 0
    PROJECT_ANALYSIS = 1
    SEMANTIC_RESTRUCTURE = 2
    QA_CHECK = 3
    DUBBING = 4
    AUDIT = 5
    COMPLETE = 6


@dataclass
class WorkflowState:
    """工作流状态"""
    project_dir: str
    current_step: int = 0
    mode: Optional[str] = None  # "A" or "B"
    qa_passed: bool = False
    attempts: int = 0
    max_attempts: int = 3
    last_error: Optional[str] = None
    history: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowState":
        return cls(**data)


def load_workflow_state(project_dir: str) -> WorkflowState:
    """
    加载工作流状态
    
    Args:
        project_dir: 项目目录
        
    Returns:
        WorkflowState 对象
    """
    state_path = os.path.join(project_dir, "workflow_state.json")
    
    if os.path.exists(state_path):
        with open(state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return WorkflowState.from_dict(data)
    
    return WorkflowState(project_dir=project_dir)


def save_workflow_state(state: WorkflowState) -> None:
    """
    保存工作流状态
    
    Args:
        state: WorkflowState 对象
    """
    state_path = os.path.join(state.project_dir, "workflow_state.json")
    
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, indent=2, ensure_ascii=False)


def advance_step(state: WorkflowState, success: bool = True, error: Optional[str] = None) -> WorkflowState:
    """
    推进工作流步骤
    
    Args:
        state: 当前状态
        success: 当前步骤是否成功
        error: 错误信息（如果失败）
        
    Returns:
        更新后的状态
    """
    # 记录历史
    state.history.append({
        "step": state.current_step,
        "success": success,
        "error": error,
    })
    
    if success:
        state.current_step += 1
        state.last_error = None
        state.attempts = 0
    else:
        state.last_error = error
        state.attempts += 1
    
    save_workflow_state(state)
    return state


def run_step_analysis(state: WorkflowState) -> Dict[str, Any]:
    """
    执行项目分析步骤
    
    Args:
        state: 工作流状态
        
    Returns:
        分析结果
    """
    metrics = analyze_project(state.project_dir)
    recommendation = recommend_mode(metrics)
    
    # 更新状态
    state.mode = recommendation.mode
    save_workflow_state(state)
    
    return {
        "metrics": asdict(metrics),
        "recommendation": asdict(recommendation),
    }


def run_step_qa(state: WorkflowState, srt_path: str, voice_map_path: Optional[str] = None) -> Dict[str, Any]:
    """
    执行 QA 检查步骤
    
    Args:
        state: 工作流状态
        srt_path: SRT 文件路径
        voice_map_path: voice_map.json 路径
        
    Returns:
        QA 报告
    """
    # 根据模式设置限制
    if state.mode == "B":
        max_chars = 100
        max_duration_ms = 6000
    else:
        max_chars = 250
        max_duration_ms = 15000
    
    report = run_qa_checks(
        srt_path=srt_path,
        voice_map_path=voice_map_path,
        max_chars=max_chars,
        max_duration_ms=max_duration_ms,
    )
    
    # 更新状态
    state.qa_passed = report.all_passed
    save_workflow_state(state)
    
    return asdict(report)


def get_dubbing_command(state: WorkflowState, srt_path: str, video_path: str, output_path: str, voice: str = "zh-CN-YunjianNeural", voice_map_path: Optional[str] = None) -> str:
    """
    生成配音命令
    
    Args:
        state: 工作流状态
        srt_path: SRT 文件路径
        video_path: 视频文件路径
        output_path: 输出路径
        voice: TTS 音色
        voice_map_path: voice_map.json 路径
        
    Returns:
        CLI 命令字符串
    """
    cmd_parts = [
        "python -m flexdub merge",
        f'"{srt_path}"',
        f'"{video_path}"',
        "--backend edge_tts",
        f"--voice {voice}",
    ]
    
    if state.mode == "B":
        cmd_parts.extend([
            "--mode elastic-video",
            "--no-rebalance",
        ])
    else:
        cmd_parts.append("--clustered")
    
    if voice_map_path:
        cmd_parts.extend([
            f'--voice-map "{voice_map_path}"',
            "--keep-brackets",
        ])
    
    cmd_parts.append(f'-o "{output_path}"')
    
    return " \\\n  ".join(cmd_parts)


def should_retry(state: WorkflowState) -> bool:
    """
    判断是否应该重试
    
    Args:
        state: 工作流状态
        
    Returns:
        True 如果应该重试
    """
    return state.attempts < state.max_attempts


def get_current_step_name(state: WorkflowState) -> str:
    """
    获取当前步骤名称
    
    Args:
        state: 工作流状态
        
    Returns:
        步骤名称
    """
    step_names = {
        0: "初始化",
        1: "项目分析",
        2: "语义重构",
        3: "QA 检查",
        4: "配音合成",
        5: "质量审计",
        6: "完成",
    }
    return step_names.get(state.current_step, "未知")
