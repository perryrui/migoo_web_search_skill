"""
Query 改写模块 - 使用智谱 GLM-4.7

两种模式:
1. 有 GLM API Key → 用 LLM 智能改写
2. 没有 Key → 用简单规则改写
"""
import json
import re
import httpx


def _extract_json_from_text(text: str):
    """从可能带前后缀的文本中提取第一个 JSON 对象"""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start == -1:
        raise ValueError("未找到 JSON 对象")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError("JSON 括号不匹配")


class QueryRewriter:
    """将用户的自然语言问题改写为搜索引擎友好的 query"""

    def __init__(self, llm_api_key: str = None, llm_model: str = None):
        self.llm_api_key = llm_api_key
        # 智谱可用模型: glm-4-flash, glm-4, glm-4-long 等；glm-4.7 可能不可用
        self.llm_model = llm_model or "glm-4-flash"
    
    async def rewrite(
        self,
        user_query: str,
        user_location: str = None,
        user_language: str = "zh-cn",
    ) -> dict:
        if self.llm_api_key:
            return await self._rewrite_with_llm(user_query, user_location, user_language)
        else:
            return self._rewrite_with_rules(user_query, user_location, user_language)
    
    async def _rewrite_with_llm(
        self,
        user_query: str,
        user_location: str = None,
        user_language: str = "zh-cn",
    ) -> dict:
        """使用智谱 GLM 进行智能改写"""
        try:
            location_hint = f"\n用户位置: {user_location}" if user_location else ""
            
            prompt = f"""你是一个专业的搜索引擎 query 优化专家。你的任务是把用户的自然语言问题改写成 1～3 个最适合在搜索引擎中使用的查询词，并给出搜索语言、时间范围和类型。

## 用户问题
{user_query}{location_hint}

## 你的任务
1. 理解用户真实意图，提炼出可被搜索引擎直接使用的关键词或短语。
2. 若问题包含多个子问题或需要多步信息，拆成多个独立、简短的搜索词（每个 1～6 个词为佳）。
3. 去掉口语化、客套话、重复信息，只保留对检索有帮助的核心词。
4. 根据问题内容判断：用中文搜索还是英文搜索效果更好；是否需要时间过滤；是普通搜索还是新闻搜索。

## 必须遵守的规则
- 搜索词要简短、具体，避免长句或问句形式。
- 中文生活/时事/本地类问题 → 用中文查询，language 填 "zh-cn"。
- 技术、编程、英文资料、国际话题 → 用英文查询，language 填 "en"。
- 若问题涉及「最近、今天、本周、刚刚、新闻、最新消息」等 → 在 time_filter 中填 "d"（一天）、"w"（一周）或 "m"（一月），否则填 null。
- 若明显是新闻/时事类 → search_type 填 "news"，否则填 "search"。
- 若提供了用户位置且问题与地点相关（如附近、推荐、天气、本地）→ 可在某个 search_query 中合理融入位置信息。

## 输出格式（仅输出以下 JSON，不要 markdown 代码块、不要前后解释）
{{
    "search_queries": ["改写后的查询1", "改写后的查询2"],
    "language": "zh-cn 或 en",
    "time_filter": null 或 "d" 或 "w" 或 "m",
    "search_type": "search 或 news"
}}

## 示例

例1 - 多步信息需求、需时间过滤：
用户问：「成龙最近一部电影的女主角近两年演了什么电影？」
输出：{{"search_queries": ["成龙 最新电影 2024 2025", "成龙新电影 女主角"], "language": "zh-cn", "time_filter": "m", "search_type": "search"}}

例2 - 技术类用英文搜：
用户问：「Python asyncio 教程」
输出：{{"search_queries": ["Python asyncio tutorial"], "language": "en", "time_filter": null, "search_type": "search"}}

例3 - 本地 + 天气：
用户问：「北京今天天气怎么样」
用户位置：北京海淀
输出：{{"search_queries": ["北京今天天气", "北京海淀天气预报"], "language": "zh-cn", "time_filter": "d", "search_type": "search"}}

例4 - 新闻类：
用户问：「特斯拉最新裁员新闻」
输出：{{"search_queries": ["特斯拉 裁员 2025", "Tesla layoffs news"], "language": "zh-cn", "time_filter": "w", "search_type": "news"}}

请针对上述「用户问题」直接输出一行 JSON，不要其他内容。"""

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.llm_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.llm_model,
                        "messages": [
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.1,
                        "max_tokens": 300,
                    },
                )
                response.raise_for_status()
                data = response.json()
            
            text = data["choices"][0]["message"]["content"].strip()
            
            # 清理 markdown 代码块标记
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            text = text.strip()
            
            if not text:
                raise ValueError("模型返回内容为空（请检查 API 密钥、模型名是否可用，如 glm-4 / glm-4-flash）")
            
            result = _extract_json_from_text(text)
            
            if "search_queries" not in result or not result["search_queries"]:
                raise ValueError("Missing search_queries")
            
            return {
                "search_queries": result["search_queries"][:3],
                "language": result.get("language", "zh-cn"),
                "time_filter": result.get("time_filter"),
                "search_type": result.get("search_type", "search"),
            }
        
        except httpx.HTTPStatusError as e:
            err_detail = ""
            try:
                body = e.response.json()
                if isinstance(body, dict) and "error" in body:
                    err_detail = body["error"].get("message", str(body))
                else:
                    err_detail = e.response.text[:200]
            except Exception:
                err_detail = e.response.text[:200] if e.response else ""
            print(f"⚠️ LLM 改写失败 [HTTP {e.response.status_code}]: {err_detail}，回退到规则改写")
            return self._rewrite_with_rules(user_query, user_location, user_language)
        except json.JSONDecodeError as e:
            raw_preview = (text[:300] + "…") if len(text) > 300 else text
            print(f"⚠️ LLM 改写失败 [JSON 解析]: {e}，模型返回预览: {raw_preview}，回退到规则改写")
            return self._rewrite_with_rules(user_query, user_location, user_language)
        except ValueError as e:
            raw_preview = (text[:300] + "…") if len(text) > 300 else text
            print(f"⚠️ LLM 改写失败 [内容校验]: {e}，模型返回预览: {raw_preview}，回退到规则改写")
            return self._rewrite_with_rules(user_query, user_location, user_language)
            print(f"⚠️ LLM 改写失败 [响应结构异常]: {e}，回退到规则改写")
            return self._rewrite_with_rules(user_query, user_location, user_language)
        except Exception as e:
            print(f"⚠️ LLM 改写失败 [{type(e).__name__}]: {e}，回退到规则改写")
            return self._rewrite_with_rules(user_query, user_location, user_language)
    
    def _rewrite_with_rules(
        self,
        user_query: str,
        user_location: str = None,
        user_language: str = "zh-cn",
    ) -> dict:
        """简单规则改写 (不需要 LLM)"""
        query = user_query.strip()
        
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', query))
        is_chinese = chinese_chars > len(query) * 0.3
        language = "zh-cn" if is_chinese else "en"
        
        time_filter = None
        news_keywords = ["最新", "今天", "今日", "昨天", "本周",
                         "latest", "today", "yesterday", "this week",
                         "新闻", "news", "刚刚", "breaking"]
        for kw in news_keywords:
            if kw in query.lower():
                time_filter = "w"
                break
        if query.startswith("最近"):
            time_filter = "m"
        
        search_type = "search"
        if any(kw in query for kw in ["新闻", "news", "最新消息", "事件"]):
            search_type = "news"
        
        search_queries = [query]
        
        if len(query) > 15:
            simplified = query
            prefix_words = ["请问", "帮我查一下", "帮我查", "帮我搜一下",
                          "帮我搜", "帮我", "我想知道", "可以告诉我",
                          "你能帮我", "能不能帮我"]
            for word in prefix_words:
                if simplified.startswith(word):
                    simplified = simplified[len(word):].strip()
                    break
            if simplified and simplified != query:
                search_queries.insert(0, simplified)
        
        if user_location:
            location_keywords = ["附近", "周围", "哪里", "推荐", "餐厅", "酒店",
                               "near", "nearby", "restaurant", "hotel"]
            if any(kw in query for kw in location_keywords):
                search_queries.append(f"{query} {user_location}")
        
        return {
            "search_queries": search_queries[:3],
            "language": language,
            "time_filter": time_filter,
            "search_type": search_type,
        }


async def _test():
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    llm_key = os.getenv("GLM_API_KEY")
    rewriter = QueryRewriter(llm_api_key=llm_key)
    
    test_queries = [
        "北京今天天气怎么样",
        "成龙最近一部电影的女主角近两年演了什么电影?",
        "Python asyncio 教程",
    ]
    
    mode = "GLM-4.7" if llm_key else "规则"
    print(f"使用 {mode} 模式改写:\n")
    
    for q in test_queries:
        result = await rewriter.rewrite(q, user_location="北京海淀")
        print(f"原始: {q}")
        print(f"改写: {result}")
        print()

if __name__ == "__main__":
    import asyncio
    asyncio.run(_test())
