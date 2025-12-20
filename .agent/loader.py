"""
Agent Skills Loader

实现渐进式披露（Progressive Disclosure）机制：
- 第一层：加载 index.yaml 元数据（启动时）
- 第二层：按需加载 SKILL.md 内容（任务触发时）
- 第三层：执行 scripts/ 中的脚本（执行时）
"""

import os
import re
import yaml
from dataclasses import dataclass
from typing import Dict, List, Optional, Any


@dataclass
class SkillMeta:
    """技能元数据（第一层）"""
    name: str
    description: str
    path: str
    triggers: List[str]
    scripts: List[str] = None
    mcp_tools: List[str] = None


@dataclass
class SkillContent:
    """技能完整内容（第二层）"""
    meta: SkillMeta
    frontmatter: Dict[str, Any]
    body: str


class SkillLoader:
    """
    技能加载器
    
    实现渐进式披露：
    1. load_index() - 加载元数据索引
    2. match_skill() - 根据触发词匹配技能
    3. load_skill() - 按需加载完整技能内容
    """
    
    def __init__(self, agent_dir: str = ".agent"):
        self.agent_dir = agent_dir
        self.index_path = os.path.join(agent_dir, "skills", "index.yaml")
        self._index: Dict[str, SkillMeta] = {}
        self._cache: Dict[str, SkillContent] = {}
    
    def load_index(self) -> Dict[str, SkillMeta]:
        """
        加载技能索引（第一层）
        
        Returns:
            技能名称到元数据的映射
        """
        if self._index:
            return self._index
        
        if not os.path.exists(self.index_path):
            return {}
        
        with open(self.index_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        for skill_data in data.get("skills", []):
            meta = SkillMeta(
                name=skill_data["name"],
                description=skill_data["description"],
                path=skill_data["path"],
                triggers=skill_data.get("triggers", []),
                scripts=skill_data.get("scripts"),
                mcp_tools=skill_data.get("mcp_tools"),
            )
            self._index[meta.name] = meta
        
        return self._index
    
    def match_skill(self, query: str) -> Optional[SkillMeta]:
        """
        根据查询匹配技能
        
        Args:
            query: 用户查询或任务描述
            
        Returns:
            匹配的技能元数据，如果没有匹配则返回 None
        """
        if not self._index:
            self.load_index()
        
        query_lower = query.lower()
        
        for meta in self._index.values():
            for trigger in meta.triggers:
                if trigger.lower() in query_lower:
                    return meta
        
        return None
    
    def load_skill(self, name: str) -> Optional[SkillContent]:
        """
        加载技能完整内容（第二层）
        
        Args:
            name: 技能名称
            
        Returns:
            技能完整内容，如果不存在则返回 None
        """
        # 检查缓存
        if name in self._cache:
            return self._cache[name]
        
        # 获取元数据
        if not self._index:
            self.load_index()
        
        meta = self._index.get(name)
        if not meta:
            return None
        
        # 读取 SKILL.md
        if not os.path.exists(meta.path):
            return None
        
        with open(meta.path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 解析 frontmatter
        frontmatter, body = self._parse_frontmatter(content)
        
        skill = SkillContent(
            meta=meta,
            frontmatter=frontmatter,
            body=body,
        )
        
        # 缓存
        self._cache[name] = skill
        return skill
    
    def _parse_frontmatter(self, content: str) -> tuple:
        """解析 YAML frontmatter"""
        pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
        match = re.match(pattern, content, re.DOTALL)
        
        if match:
            frontmatter = yaml.safe_load(match.group(1))
            body = match.group(2)
            return frontmatter, body
        
        return {}, content
    
    def list_skills(self) -> List[Dict[str, str]]:
        """
        列出所有技能（用于 Agent 感知）
        
        Returns:
            技能摘要列表
        """
        if not self._index:
            self.load_index()
        
        return [
            {"name": meta.name, "description": meta.description}
            for meta in self._index.values()
        ]
    
    def get_skill_for_task(self, task: str) -> Optional[str]:
        """
        为任务推荐技能
        
        Args:
            task: 任务描述
            
        Returns:
            推荐的技能内容（Markdown），如果没有匹配则返回 None
        """
        meta = self.match_skill(task)
        if not meta:
            return None
        
        skill = self.load_skill(meta.name)
        if not skill:
            return None
        
        return skill.body


# 便捷函数
def get_loader() -> SkillLoader:
    """获取全局加载器实例"""
    return SkillLoader()


def match_and_load(query: str) -> Optional[str]:
    """
    匹配并加载技能（一步完成）
    
    Args:
        query: 用户查询
        
    Returns:
        技能内容（Markdown）
    """
    loader = get_loader()
    return loader.get_skill_for_task(query)
