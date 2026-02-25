"""
Serper.dev 搜索模块
"""
import httpx
from models import SearchSource


class SerperSearch:
    BASE_URL = "https://google.serper.dev/search"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    async def search(
        self,
        query: str,
        num_results: int = 8,
        search_type: str = "search",
        country: str = None,
        language: str = None,
        time_period: str = None,
    ) -> list[SearchSource]:
        payload = {"q": query, "num": num_results}
        if country:
            payload["gl"] = country
        if language:
            payload["hl"] = language
        if time_period:
            payload["tbs"] = f"qdr:{time_period}"
        
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(self.BASE_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        
        results = []
        for i, item in enumerate(data.get("organic", [])):
            results.append(SearchSource(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
                position=i + 1,
            ))
        return results


async def _test():
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    key = os.getenv("SERPER_API_KEY")
    if not key:
        print("❌ 请先在 .env 文件中设置 SERPER_API_KEY")
        return
    
    searcher = SerperSearch(key)
    results = await searcher.search("2025年中国GDP增速", num_results=5, language="zh-cn")
    
    print(f"✅ 搜索到 {len(results)} 条结果:\n")
    for r in results:
        print(f"  [{r.position}] {r.title}")
        print(f"      {r.url}")
        print(f"      {r.snippet[:100]}...")
        print()

if __name__ == "__main__":
    import asyncio
    asyncio.run(_test())
