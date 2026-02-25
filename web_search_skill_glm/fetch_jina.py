"""
Jina Reader 网页内容抓取模块
用法: 请求 https://r.jina.ai/{url} 拿到网页的 markdown 正文
"""
import asyncio
import httpx
from models import FetchedContent


class JinaFetcher:
    BASE_URL = "https://r.jina.ai"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
    
    @staticmethod
    def _clean_content(text: str) -> str:
        """清洗网页内容，去掉导航栏、菜单、页脚等噪音"""
        lines = text.split("\n")
        cleaned = []
        consecutive_short_links = 0
        
        for line in lines:
            stripped = line.strip()
            
            # 跳过连续的短链接行 (导航菜单)
            if stripped.startswith("[") and stripped.endswith(")") and len(stripped) < 80:
                consecutive_short_links += 1
                if consecutive_short_links > 3:
                    continue
            else:
                consecutive_short_links = 0
            
            # 跳过纯图片行
            if stripped.startswith("![") and "](" in stripped:
                continue
            
            # 跳过 blob: 链接
            if "blob:" in stripped:
                continue
            
            cleaned.append(line)
        
        return "\n".join(cleaned)
    
    async def fetch_one(
        self,
        url: str,
        timeout: float = 15.0,
        max_length: int = 8000,
    ) -> FetchedContent:
        headers = {
            "Accept": "text/plain",
            "X-Return-Format": "markdown",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        jina_url = f"{self.BASE_URL}/{url}"
        
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(jina_url, headers=headers)
                response.raise_for_status()
                
                content = response.text
                content = self._clean_content(content)
                
                if len(content) > max_length:
                    content = content[:max_length] + "\n\n...[内容已截断]"
                
                title = ""
                for line in content.split("\n"):
                    if line.strip().startswith("#"):
                        title = line.strip().lstrip("#").strip()
                        break
                    elif line.strip():
                        title = line.strip()[:100]
                        break
                
                return FetchedContent(
                    url=url, title=title, content=content,
                    word_count=len(content), success=True,
                )
        
        except httpx.TimeoutException:
            return FetchedContent(url=url, title="", content="", word_count=0, success=False, error=f"超时 ({timeout}s)")
        except httpx.HTTPStatusError as e:
            return FetchedContent(url=url, title="", content="", word_count=0, success=False, error=f"HTTP {e.response.status_code}")
        except Exception as e:
            return FetchedContent(url=url, title="", content="", word_count=0, success=False, error=str(e))
    
    async def fetch_many(
        self,
        urls: list[str],
        max_concurrent: int = 5,
        timeout: float = 15.0,
        max_length: int = 8000,
    ) -> list[FetchedContent]:
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def _fetch(url: str) -> FetchedContent:
            async with semaphore:
                return await self.fetch_one(url, timeout=timeout, max_length=max_length)
        
        tasks = [_fetch(url) for url in urls]
        return list(await asyncio.gather(*tasks))


async def _test():
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    fetcher = JinaFetcher(api_key=os.getenv("JINA_API_KEY"))
    print("正在抓取测试页面...")
    result = await fetcher.fetch_one("https://en.wikipedia.org/wiki/Python_(programming_language)")
    
    if result.success:
        print(f"✅ 抓取成功! 标题: {result.title}, 字数: {result.word_count}")
        print(f"前 300 字:\n{result.content[:300]}...")
    else:
        print(f"❌ 抓取失败: {result.error}")

if __name__ == "__main__":
    asyncio.run(_test())
