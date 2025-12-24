#!/usr/bin/env python3
"""
MCP 工具链验证脚本

验证 FlexDub MCP 服务器的工具是否正常工作。
"""

import json
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flexdub.mcp.server import FlexDubMCPServer, ToolResult


def test_list_tools():
    """测试工具列表"""
    print("=" * 50)
    print("测试: list_tools")
    print("=" * 50)
    
    server = FlexDubMCPServer()
    tools = server.list_tools()
    
    print(f"可用工具数量: {len(tools)}")
    for tool in tools:
        print(f"  - {tool['name']}: {tool['description']}")
    
    assert len(tools) >= 4, "应该至少有 4 个工具"
    print("✅ PASSED\n")


def test_recommend_mode():
    """测试模式推荐"""
    print("=" * 50)
    print("测试: recommend_mode")
    print("=" * 50)
    
    server = FlexDubMCPServer()
    
    # 测试 Mode A 场景 (低 CPM)
    result = server.call_tool("recommend_mode", {
        "avg_cpm": 180,
        "max_cpm": 250,
        "duration_ms": 120000,
    })
    
    assert result.success, f"调用失败: {result.error}"
    assert result.data["mode"] == "A", f"期望 Mode A，得到 {result.data['mode']}"
    print(f"低 CPM 场景: {json.dumps(result.data, indent=2, ensure_ascii=False)}")
    
    # 测试 Mode B 场景 (高 CPM)
    result = server.call_tool("recommend_mode", {
        "avg_cpm": 280,
        "max_cpm": 350,
        "duration_ms": 120000,
    })
    
    assert result.success, f"调用失败: {result.error}"
    assert result.data["mode"] == "B", f"期望 Mode B，得到 {result.data['mode']}"
    print(f"高 CPM 场景: {json.dumps(result.data, indent=2, ensure_ascii=False)}")
    
    print("✅ PASSED\n")


def test_diagnose_error():
    """测试错误诊断"""
    print("=" * 50)
    print("测试: diagnose_error")
    print("=" * 50)
    
    server = FlexDubMCPServer()
    
    # 测试 TTS 失败诊断
    result = server.call_tool("diagnose_error", {
        "error_type": "tts_failed",
        "error_message": "Edge TTS synthesis failed",
    })
    
    assert result.success, f"调用失败: {result.error}"
    assert "diagnosis" in result.data
    print(f"TTS 失败诊断: {json.dumps(result.data, indent=2, ensure_ascii=False)}")
    
    # 测试同步偏差诊断
    result = server.call_tool("diagnose_error", {
        "error_type": "sync_drift",
        "error_message": "|delta_ms| > 180ms",
    })
    
    assert result.success, f"调用失败: {result.error}"
    print(f"同步偏差诊断: {json.dumps(result.data, indent=2, ensure_ascii=False)}")
    
    # 测试未知错误
    result = server.call_tool("diagnose_error", {
        "error_type": "unknown_error",
    })
    
    assert result.success, f"调用失败: {result.error}"
    print(f"未知错误诊断: {json.dumps(result.data, indent=2, ensure_ascii=False)}")
    
    print("✅ PASSED\n")


def test_tool_errors():
    """测试错误处理"""
    print("=" * 50)
    print("测试: 错误处理")
    print("=" * 50)
    
    server = FlexDubMCPServer()
    
    # 测试未知工具
    result = server.call_tool("unknown_tool", {})
    assert not result.success
    assert "Unknown tool" in result.error
    print(f"未知工具错误: {result.error}")
    
    # 测试缺少必需参数
    result = server.call_tool("recommend_mode", {})
    assert not result.success
    print(f"缺少参数错误: {result.error}")
    
    print("✅ PASSED\n")


def main():
    """运行所有测试"""
    print("\n" + "=" * 50)
    print("FlexDub MCP 工具链验证")
    print("=" * 50 + "\n")
    
    tests = [
        test_list_tools,
        test_recommend_mode,
        test_diagnose_error,
        test_tool_errors,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {e}\n")
            failed += 1
        except Exception as e:
            print(f"❌ ERROR: {e}\n")
            failed += 1
    
    print("=" * 50)
    print(f"结果: {passed} 通过, {failed} 失败")
    print("=" * 50)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
