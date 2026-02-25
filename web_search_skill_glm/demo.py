"""
交互式 Demo - 在终端测试 Web Search Skill

运行: python3 demo.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from web_search_skill import WebSearchSkill


async def interactive_demo():
    print("=" * 60)
    print("🔍 Web Search Skill - 交互式 Demo (GLM-4.7 + Serper + Jina)")
    print("=" * 60)
    print()
    
    try:
        skill = WebSearchSkill()
        print("✅ 初始化成功!\n")
    except ValueError as e:
        print(f"\n{e}")
        print("\n请按照以下步骤配置:")
        print("1. cp .env.example .env")
        print("2. 编辑 .env 填入 API Keys")
        print("3. python3 demo.py")
        return
    
    print("输入搜索问题 (q=退出, v=切换详细模式):\n")
    verbose = True
    
    while True:
        try:
            query = input("🔎 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见!")
            break
        
        if not query:
            continue
        if query.lower() == "q":
            print("再见!")
            break
        if query.lower() == "v":
            verbose = not verbose
            print(f"详细模式: {'开启' if verbose else '关闭'}")
            continue
        
        print()
        try:
            result = await skill.search(query=query, verbose=verbose)
            
            print("\n" + "=" * 60)
            print("📋 搜索结果 (传给 Main Agent 的内容):")
            print("=" * 60)
            
            context = result.to_context_string()
            if len(context) > 2000:
                print(context[:2000])
                print(f"\n... [还有 {len(context) - 2000} 字符]")
            else:
                print(context)
            
            print("\n📎 引用来源:")
            for ref in result.get_reference_list():
                print(f"  [{ref['index']}] {ref['title'][:60]}")
                print(f"      {ref['url']}")
            
            print(f"\n📊 统计: {len(result.sources)} 条搜索结果, "
                  f"{sum(1 for c in result.contents if c.success)} 篇正文抓取成功")
        except Exception as e:
            print(f"❌ 搜索出错: {e}")
            import traceback
            traceback.print_exc()
        print()


if __name__ == "__main__":
    asyncio.run(interactive_demo())
