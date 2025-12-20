"""
术语保留规则

从 agent_manual.md 提取的硬编码术语列表。
这些术语在语义重构时必须保持英文原文。
"""

# 3D 软件名称
SOFTWARE_3D = {
    "Maya", "Blender", "ZBrush", "3ds Max", "Houdini", 
    "Cinema 4D", "Modo", "Substance Painter", "Substance Designer",
    "Marvelous Designer", "RizomUV", "TopoGun",
}

# 2D 软件名称
SOFTWARE_2D = {
    "Photoshop", "Illustrator", "After Effects", "Premiere Pro",
    "Figma", "Sketch", "InDesign", "Lightroom",
}

# 游戏引擎
GAME_ENGINES = {
    "Unity", "Unreal Engine", "Godot", "CryEngine", "Lumberyard",
}

# Maya 工具名称
MAYA_TOOLS = {
    "Quad Draw", "Live Surface", "Modeling Toolkit", "Soft Select",
    "Smooth Mesh Preview", "Crease Tool", "Multi-Cut Tool",
    "Target Weld", "Merge Vertices", "Bridge", "Fill Hole",
    "Outliner", "Hypershade", "Node Editor", "UV Editor",
    "Graph Editor", "Dope Sheet", "Time Slider",
}

# ZBrush 工具名称
ZBRUSH_TOOLS = {
    "ZRemesher", "DynaMesh", "ZModeler", "Sculptris Pro",
    "Polygroups", "SubTool", "ZSphere", "Shadowbox",
    "Decimation Master", "UV Master",
}

# 通用工具名称
GENERAL_TOOLS = {
    "UV Editor", "Node Editor", "Outliner", "Timeline",
    "Properties Panel", "Tool Settings", "Viewport",
}

# 拓扑术语
TOPOLOGY_TERMS = {
    "Retopology", "Quads", "N-gons", "Poles", "Edge Flow",
    "Edge Loop", "Edge Ring", "Topology", "Mesh", "Polygon",
    "Vertex", "Face", "Normal", "Subdivision", "LOD",
}

# 动画术语
ANIMATION_TERMS = {
    "Rigging", "Skinning", "Blend Shapes", "Morph Targets",
    "IK", "FK", "Keyframe", "Animation Curve", "Constraint",
    "Joint", "Bone", "Weight Painting",
}

# 渲染术语
RENDERING_TERMS = {
    "Subsurface Scattering", "PBR", "HDRI", "Ray Tracing",
    "Global Illumination", "Ambient Occlusion", "Normal Map",
    "Displacement Map", "Roughness", "Metallic", "Albedo",
    "Specular", "Fresnel", "BRDF",
}

# 快捷键模式
SHORTCUT_PATTERNS = [
    r"Ctrl\s*\+\s*\w",
    r"Shift\s*\+\s*\w",
    r"Alt\s*\+\s*\w",
    r"Cmd\s*\+\s*\w",
    r"Tab\s*键",
    r"\d\s*键",
]

# 全大写缩写（保持原样）
UPPERCASE_ABBREVIATIONS = {
    "UV", "PBR", "HDRI", "TTS", "SRT", "CPM", "FFmpeg",
    "API", "LLM", "JSON", "MP4", "WAV", "MP3", "AAC",
    "RGB", "RGBA", "HDR", "EXR", "FBX", "OBJ", "GLTF",
    "IK", "FK", "LOD", "VFX", "CGI", "GPU", "CPU",
}

# 合并所有术语
ALL_PRESERVED_TERMS = (
    SOFTWARE_3D | SOFTWARE_2D | GAME_ENGINES |
    MAYA_TOOLS | ZBRUSH_TOOLS | GENERAL_TOOLS |
    TOPOLOGY_TERMS | ANIMATION_TERMS | RENDERING_TERMS |
    UPPERCASE_ABBREVIATIONS
)


def should_preserve_term(term: str) -> bool:
    """
    检查术语是否应该保留英文
    
    Args:
        term: 要检查的术语
        
    Returns:
        True 如果应该保留英文
    """
    # 精确匹配
    if term in ALL_PRESERVED_TERMS:
        return True
    
    # 全大写缩写
    if term.isupper() and len(term) >= 2:
        return True
    
    # 驼峰命名
    if any(c.isupper() for c in term[1:]) and term[0].isupper():
        return True
    
    return False


def get_terminology_list() -> list:
    """获取所有保留术语列表"""
    return sorted(ALL_PRESERVED_TERMS)
