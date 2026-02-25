"""数据模型定义"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SearchSource:
    """单个搜索结果"""
    title: str
    url: str
    snippet: str
    position: int


@dataclass
class FetchedContent:
    """抓取到的网页内容"""
    url: str
    title: str
    content: str
    word_count: int
    success: bool
    error: Optional[str] = None


@dataclass
class SearchResult:
    """最终返回给 Main Agent 的结构化结果"""
    query: str
    search_queries: list[str]
    sources: list[SearchSource] = field(default_factory=list)
    contents: list[FetchedContent] = field(default_factory=list)
    
    def to_context_string(self, max_tokens_per_source: int = 1500) -> str:
        """转换为可以直接塞进 Main Agent prompt 的文本"""
        parts = []
        parts.append(f"## 搜索结果 (Query: {self.query})\n")
        
        for i, content in enumerate(self.contents):
            if not content.success:
                continue
            text = content.content
            if len(text) > max_tokens_per_source * 4:
                text = text[:max_tokens_per_source * 4] + "\n...[内容已截断]"
            
            parts.append(f"### Source [{i+1}]: {content.title}")
            parts.append(f"URL: {content.url}")
            parts.append(f"{text}\n")
        
        if not any(c.success for c in self.contents):
            parts.append("### 搜索摘要 (未能抓取正文，以下为搜索引擎摘要):\n")
            for i, source in enumerate(self.sources):
                parts.append(f"[{i+1}] {source.title}")
                parts.append(f"    URL: {source.url}")
                parts.append(f"    {source.snippet}\n")
        
        return "\n".join(parts)
    
    def get_reference_list(self) -> list[dict]:
        """返回引用列表"""
        refs = []
        for i, content in enumerate(self.contents):
            if content.success:
                refs.append({
                    "index": i + 1,
                    "title": content.title,
                    "url": content.url,
                })
        return refs
