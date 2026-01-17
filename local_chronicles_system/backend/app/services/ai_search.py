"""
AI搜索服务 - 智能解析用户查询
"""
import json
from typing import Dict, List, Any, Optional
from loguru import logger
import openai
from app.core.config import settings, CATEGORY_CONFIG


class AISearchService:
    """AI搜索服务"""
    
    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
    
    async def parse_search_query(self, query: str) -> Dict[str, Any]:
        """解析用户的自然语言查询"""
        
        system_prompt = """你是一个搜索查询解析助手。请分析用户的查询意图，提取搜索条件。

可用的搜索字段：
- region: 地区（如"辽宁葫芦岛市"）
- year: 年份（2000-2050）
- year_range: 年份范围 {start, end}
- work_category: 工作类别（农业/工业/服务业/科技/教育/医疗/金融/交通/建筑/其他）
- unit: 单位名称
- person: 人物姓名
- income_range: 收入范围 {min, max}
- keywords: 关键词数组

请返回JSON格式的解析结果。只提取明确的查询条件，不确定的不要添加。"""

        user_prompt = f"请解析以下查询：{query}"
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            result = response.choices[0].message.content
            parsed = json.loads(result)
            
            return self._validate_parsed_query(parsed)
            
        except Exception as e:
            logger.error(f"AI解析查询失败: {e}")
            # 降级处理：简单关键词提取
            return self._simple_parse(query)
    
    def _validate_parsed_query(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """验证解析结果"""
        validated = {}
        
        if parsed.get("region"):
            validated["region"] = str(parsed["region"])
        
        if parsed.get("year"):
            try:
                year = int(parsed["year"])
                if 2000 <= year <= 2050:
                    validated["year"] = year
            except:
                pass
        
        if parsed.get("year_range"):
            year_range = parsed["year_range"]
            validated["year_range"] = {}
            if year_range.get("start"):
                try:
                    validated["year_range"]["start"] = int(year_range["start"])
                except:
                    pass
            if year_range.get("end"):
                try:
                    validated["year_range"]["end"] = int(year_range["end"])
                except:
                    pass
        
        if parsed.get("work_category"):
            category = parsed["work_category"]
            valid_categories = CATEGORY_CONFIG["工作类别"]["values"]
            if category in valid_categories:
                validated["work_category"] = category
        
        if parsed.get("unit"):
            validated["unit"] = str(parsed["unit"])
        
        if parsed.get("person"):
            validated["person"] = str(parsed["person"])
        
        if parsed.get("income_range"):
            income = parsed["income_range"]
            validated["income_range"] = {}
            if income.get("min") is not None:
                try:
                    validated["income_range"]["min"] = float(income["min"])
                except:
                    pass
            if income.get("max") is not None:
                try:
                    validated["income_range"]["max"] = float(income["max"])
                except:
                    pass
        
        if parsed.get("keywords"):
            keywords = parsed["keywords"]
            if isinstance(keywords, list):
                validated["keywords"] = [str(k) for k in keywords[:10]]
            elif isinstance(keywords, str):
                validated["keywords"] = [keywords]
        
        return validated
    
    def _simple_parse(self, query: str) -> Dict[str, Any]:
        """简单的规则解析（降级方案）"""
        import re
        
        result = {"keywords": []}
        
        # 年份提取
        year_match = re.search(r'(20[0-4][0-9]|2050)年?', query)
        if year_match:
            result["year"] = int(year_match.group(1))
        
        # 年份范围
        range_match = re.search(r'(20[0-4][0-9]|2050)\s*[-到至]\s*(20[0-4][0-9]|2050)', query)
        if range_match:
            result["year_range"] = {
                "start": int(range_match.group(1)),
                "end": int(range_match.group(2))
            }
        
        # 地区提取
        region_match = re.search(r'([^\s]+(?:省|市|县|区|镇))', query)
        if region_match:
            result["region"] = region_match.group(1)
        
        # 工作类别
        for category in CATEGORY_CONFIG["工作类别"]["values"]:
            if category in query:
                result["work_category"] = category
                break
        
        # 提取关键词
        # 移除已识别的内容
        remaining = query
        if result.get("year"):
            remaining = remaining.replace(str(result["year"]), "")
        if result.get("region"):
            remaining = remaining.replace(result["region"], "")
        
        # 分词
        keywords = [w for w in remaining.split() if len(w) >= 2]
        result["keywords"] = keywords[:5]
        
        return result
    
    async def expand_query(self, query: str) -> List[str]:
        """扩展查询（同义词、相关词）"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": "请为以下查询生成3-5个相关的搜索词，用于扩展搜索范围。只返回JSON数组格式。"
                    },
                    {"role": "user", "content": query}
                ],
                temperature=0.5,
                max_tokens=200
            )
            
            result = response.choices[0].message.content
            expanded = json.loads(result)
            
            if isinstance(expanded, list):
                return expanded[:5]
            return []
            
        except:
            return []
