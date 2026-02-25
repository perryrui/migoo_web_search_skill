"""
Web Search Skill - 核心编排模块

用法:
    from web_search_skill import WebSearchSkill
    
    skill = WebSearchSkill()
    result = await skill.search("北京到曼谷的航班")
    context = result.to_context_string()  # 塞进 Main Agent prompt
"""
import os
import time
from dotenv import load_dotenv

from models import SearchResult
from query_rewriter import QueryRewriter
from search_serper import SerperSearch
from fetch_jina import JinaFetcher


class WebSearchSkill:
    
    def __init__(
        self,
        serper_api_key: str = None,
        jina_api_key: str = None,
        llm_api_key: str = None,
    ):
        load_dotenv()
        
        self.serper_key = serper_api_key or os.getenv("SERPER_API_KEY")
        self.jina_key = jina_api_key or os.getenv("JINA_API_KEY")
        self.llm_key = llm_api_key or os.getenv("GLM_API_KEY")
        
        if not self.serper_key:
            raise ValueError(
                "❌ 缺少 SERPER_API_KEY!\n"
                "   请在 .env 文件中设置，或访问 https://serper.dev 申请"
            )
        
        self.rewriter = QueryRewriter(
            llm_api_key=self.llm_key,
            llm_model=os.getenv("GLM_MODEL"),
        )
        self.searcher = SerperSearch(api_key=self.serper_key)
        self.fetcher = JinaFetcher(api_key=self.jina_key)
    
    async def search(
        self,
        query: str,
        user_location: str = None,
        user_language: str = "zh-cn",
        num_results: int = 6,
        fetch_top_n: int = 4,
        max_content_length: int = 6000,
        verbose: bool = False,
    ) -> SearchResult:
        timings = {}
        
        # Step 1: Query 改写
        t0 = time.time()
        if verbose:
            print(f"🔍 Step 1: 改写 Query...")
        
        rewrite_result = await self.rewriter.rewrite(
            query, user_location=user_location, user_language=user_language,
        )
        search_queries = rewrite_result["search_queries"]
        timings["rewrite"] = time.time() - t0
        
        if verbose:
            print(f"   改写结果: {search_queries}")
            print(f"   语言: {rewrite_result['language']}, "
                  f"时间过滤: {rewrite_result['time_filter']}, "
                  f"类型: {rewrite_result['search_type']}")
            print(f"   耗时: {timings['rewrite']:.2f}s\n")
        
        # Step 2: Serper 搜索
        t0 = time.time()
        if verbose:
            print(f"🌐 Step 2: 执行搜索...")
        
        all_sources = []
        seen_urls = set()
        
        for sq in search_queries:
            sources = await self.searcher.search(
                query=sq,
                num_results=num_results,
                language=rewrite_result["language"],
                time_period=rewrite_result["time_filter"],
            )
            for s in sources:
                if s.url not in seen_urls:
                    seen_urls.add(s.url)
                    all_sources.append(s)
        
        timings["search"] = time.time() - t0
        
        if verbose:
            print(f"   搜索到 {len(all_sources)} 条去重后的结果")
            for s in all_sources[:5]:
                print(f"   - [{s.position}] {s.title[:60]}")
            print(f"   耗时: {timings['search']:.2f}s\n")
        
        # Step 3: Jina 抓取正文
        t0 = time.time()
        if verbose:
            print(f"📄 Step 3: 抓取前 {fetch_top_n} 个页面正文...")
        
        urls_to_fetch = [s.url for s in all_sources[:fetch_top_n]]
        contents = await self.fetcher.fetch_many(
            urls=urls_to_fetch, max_concurrent=4,
            timeout=15.0, max_length=max_content_length,
        )
        
        timings["fetch"] = time.time() - t0
        
        if verbose:
            success_count = sum(1 for c in contents if c.success)
            print(f"   成功抓取: {success_count}/{len(contents)}")
            for c in contents:
                status = "✅" if c.success else f"❌ {c.error}"
                print(f"   - {status} {c.url[:60]}")
            print(f"   耗时: {timings['fetch']:.2f}s\n")
        
        total_time = sum(timings.values())
        if verbose:
            print(f"✨ 完成! 总耗时: {total_time:.2f}s")
            print(f"   (改写 {timings['rewrite']:.2f}s + "
                  f"搜索 {timings['search']:.2f}s + "
                  f"抓取 {timings['fetch']:.2f}s)")
        
        return SearchResult(
            query=query,
            search_queries=search_queries,
            sources=all_sources,
            contents=contents,
        )


async def _test():
    skill = WebSearchSkill()
    result = await skill.search("2025年中国经济增速预测", verbose=True)
    
    print("\n" + "=" * 60)
    print("📋 最终输出 (这段文本会传给 Main Agent):")
    print("=" * 60)
    print(result.to_context_string()[:2000])
    
    print("\n📎 引用列表:")
    for ref in result.get_reference_list():
        print(f"  [{ref['index']}] {ref['title'][:50]} - {ref['url']}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(_test())
