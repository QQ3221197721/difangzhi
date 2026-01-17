"""
AI数据提取服务 - 从地方志文本中提取结构化数据
"""
import json
import re
from typing import Dict, List, Any, Optional
from loguru import logger
import openai
from app.core.config import settings, CATEGORY_CONFIG


class AIExtractorService:
    """AI数据提取服务"""
    
    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
    
    async def extract_chronicle_data(self, text: str) -> Dict[str, Any]:
        """从地方志文本中提取结构化数据"""
        
        # 分块处理长文本
        chunks = self._split_text(text, max_length=3000)
        all_records = []
        
        for chunk in chunks:
            try:
                records = await self._extract_from_chunk(chunk)
                all_records.extend(records)
            except Exception as e:
                logger.error(f"提取数据失败: {e}")
                continue
        
        return {
            "records": all_records,
            "total_extracted": len(all_records)
        }
    
    async def _extract_from_chunk(self, text: str) -> List[Dict[str, Any]]:
        """从文本块中提取数据"""
        
        system_prompt = """你是一个专业的地方志数据提取助手。请从给定的地方志文本中提取结构化数据。

对于每条提取的数据记录，请提供以下字段：
- title: 标题或主题
- content: 原文内容摘要
- summary: AI生成的简要摘要
- region: 完整地区名称
- region_province: 省份
- region_city: 城市
- region_district: 区县
- year: 年份（整数，2000-2050）
- unit: 相关单位
- person: 相关人物
- income: 收入金额（数字，单位：万元）
- income_range: 收入范围（如"10-50"）
- work_category: 工作类别（农业/工业/服务业/科技/教育/医疗/金融/交通/建筑/其他）
- tags: 其他标签（JSON对象）
- numeric_data: 数值数据（JSON对象，如人口、产值等）
- confidence: 置信度（0-1之间的小数）

请以JSON数组格式返回提取的数据。如果某些字段无法确定，设为null。"""

        user_prompt = f"""请从以下地方志文本中提取结构化数据：

{text}

请返回JSON格式的数据数组。"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=settings.AI_MAX_TOKENS,
                response_format={"type": "json_object"}
            )
            
            result = response.choices[0].message.content
            data = json.loads(result)
            
            # 处理返回的数据
            records = data.get("records", data.get("data", []))
            if isinstance(records, list):
                return [self._validate_record(r) for r in records]
            
            return []
            
        except Exception as e:
            logger.error(f"AI提取失败: {e}")
            # 降级处理：使用规则提取
            return self._rule_based_extraction(text)
    
    def _validate_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """验证和清洗提取的记录"""
        validated = {}
        
        validated["title"] = str(record.get("title", "未命名记录"))[:500]
        validated["content"] = str(record.get("content", ""))[:5000] if record.get("content") else None
        validated["summary"] = str(record.get("summary", ""))[:1000] if record.get("summary") else None
        
        # 地区信息
        validated["region"] = record.get("region")
        validated["region_province"] = record.get("region_province")
        validated["region_city"] = record.get("region_city")
        validated["region_district"] = record.get("region_district")
        
        # 年份验证
        year = record.get("year")
        if year:
            try:
                year = int(year)
                if 2000 <= year <= 2050:
                    validated["year"] = year
            except:
                pass
        
        validated["unit"] = record.get("unit")
        validated["person"] = record.get("person")
        
        # 收入验证
        income = record.get("income")
        if income:
            try:
                validated["income"] = float(income)
            except:
                pass
        
        validated["income_range"] = record.get("income_range")
        
        # 工作类别验证
        work_category = record.get("work_category")
        valid_categories = CATEGORY_CONFIG["工作类别"]["values"]
        if work_category in valid_categories:
            validated["work_category"] = work_category
        
        validated["tags"] = record.get("tags", {})
        validated["numeric_data"] = record.get("numeric_data", {})
        
        # 置信度
        confidence = record.get("confidence", 0.8)
        try:
            validated["confidence"] = max(0, min(1, float(confidence)))
        except:
            validated["confidence"] = 0.8
        
        return validated
    
    def _split_text(self, text: str, max_length: int = 3000) -> List[str]:
        """将长文本分割成块"""
        if len(text) <= max_length:
            return [text]
        
        chunks = []
        # 按段落分割
        paragraphs = text.split('\n\n')
        current_chunk = ""
        
        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 <= max_length:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _rule_based_extraction(self, text: str) -> List[Dict[str, Any]]:
        """基于规则的数据提取（降级方案）"""
        records = []
        
        # 年份提取
        year_pattern = r'(20[0-4][0-9]|2050)年'
        years = re.findall(year_pattern, text)
        
        # 地区提取
        region_pattern = r'([^\s]+(?:省|市|县|区))'
        regions = re.findall(region_pattern, text)
        
        # 金额提取
        money_pattern = r'(\d+(?:\.\d+)?)\s*(?:万元|亿元)'
        amounts = re.findall(money_pattern, text)
        
        # 工作类别关键词
        category_keywords = {
            "工业": ["工厂", "制造", "生产", "工业"],
            "农业": ["农业", "种植", "养殖", "农村"],
            "服务业": ["服务", "商业", "零售"],
            "科技": ["科技", "技术", "创新", "研发"],
            "教育": ["学校", "教育", "培训"],
            "医疗": ["医院", "医疗", "卫生"],
        }
        
        detected_category = None
        for category, keywords in category_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    detected_category = category
                    break
            if detected_category:
                break
        
        # 创建基础记录
        if years or regions:
            record = {
                "title": text[:100] + "..." if len(text) > 100 else text,
                "content": text[:1000],
                "year": int(years[0]) if years else None,
                "region": regions[0] if regions else None,
                "income": float(amounts[0]) if amounts else None,
                "work_category": detected_category,
                "confidence": 0.5
            }
            records.append(record)
        
        return records
    
    async def categorize_data(self, record: Dict[str, Any]) -> Dict[str, List[str]]:
        """为数据自动分类"""
        categories = {
            "一级分类": [],
            "二级分类": []
        }
        
        # 地区分类
        if record.get("region"):
            categories["一级分类"].append("地区")
            if record.get("region_city"):
                categories["二级分类"].append(record["region_city"])
        
        # 年份分类
        if record.get("year"):
            categories["一级分类"].append("年份")
            categories["二级分类"].append(str(record["year"]))
        
        # 工作类别分类
        if record.get("work_category"):
            categories["一级分类"].append("工作类别")
            categories["二级分类"].append(record["work_category"])
        
        # 单位分类
        if record.get("unit"):
            categories["一级分类"].append("单位")
        
        # 人物分类
        if record.get("person"):
            categories["一级分类"].append("人物")
        
        # 收入分类
        if record.get("income") is not None:
            categories["一级分类"].append("收入")
            income = record["income"]
            if income < 10:
                categories["二级分类"].append("0-10")
            elif income < 50:
                categories["二级分类"].append("10-50")
            elif income < 100:
                categories["二级分类"].append("50-100")
            elif income < 500:
                categories["二级分类"].append("100-500")
            else:
                categories["二级分类"].append("500+")
        
        return categories
