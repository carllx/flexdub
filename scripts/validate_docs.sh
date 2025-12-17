#!/bin/bash
# 文档参数一致性验证脚本

set -e

echo "🔍 验证文档参数一致性..."

# 定义标准值
STANDARD_TARGET_CPM="180"
STANDARD_PANIC_CPM="300"
STANDARD_MAX_SHIFT="1000"
STANDARD_AR="48000"

# 检查函数
check_param() {
    local file=$1
    local param=$2
    local standard=$3
    local context=$4
    
    echo "  检查 $file 中的 $param..."
    
    # 查找非标准值（排除注释和场景建议）
    violations=$(grep -n "$param" "$file" | grep -v "$standard" | grep -v "#" | grep -v "建议" | grep -v "场景" || true)
    
    if [ -n "$violations" ]; then
        echo "    ⚠️  发现非标准值:"
        echo "$violations"
        return 1
    else
        echo "    ✅ 通过"
        return 0
    fi
}

# 验证 agent_manual.md
echo ""
echo "📄 验证 agent_manual.md..."
check_param "agent_manual.md" "target-cpm" "$STANDARD_TARGET_CPM" "默认值"
check_param "agent_manual.md" "panic-cpm" "$STANDARD_PANIC_CPM" "默认值"
check_param "agent_manual.md" "max-shift" "$STANDARD_MAX_SHIFT" "默认值"

# 验证 README.md
echo ""
echo "📄 验证 README.md..."
check_param "README.md" "target-cpm" "$STANDARD_TARGET_CPM" "示例命令"

# 验证 steering 文档
echo ""
echo "📄 验证 .kiro/steering/tech.md..."
check_param ".kiro/steering/tech.md" "target-cpm" "$STANDARD_TARGET_CPM" "默认参数"

# 检查参数互斥
echo ""
echo "🔍 检查参数互斥规则..."
if grep -q "keep-brackets.*strip-meta" agent_manual.md || grep -q "strip-meta.*keep-brackets" agent_manual.md; then
    echo "  ⚠️  发现 --keep-brackets 和 --strip-meta 同时使用"
else
    echo "  ✅ 无参数互斥冲突"
fi

# 检查旧路径引用
echo ""
echo "🔍 检查旧路径引用..."
if grep -q "agents/srt_dubbing_agent" agent_manual.md; then
    echo "  ⚠️  发现旧路径引用: agents/srt_dubbing_agent"
else
    echo "  ✅ 无旧路径引用"
fi

echo ""
echo "✅ 验证完成！"
