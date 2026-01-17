"""
AI助手服务 - 对话式AI交互
"""
import json
from typing import Dict, List, Any, Optional
from loguru import logger
import openai
from app.core.config import settings


class AIAssistantService:
    """AI助手服务"""
    
    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
    
    async def chat(
        self, 
        message: str, 
        history: List[Dict[str, str]] = None,
        context_data: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """与AI助手对话"""
        
        system_prompt = """你是地方志数据管理系统的AI助手，专门帮助用户：
1. 查询和分析地方志数据
2. 解释数据含义和趋势
3. 提供数据分析建议
4. 指导系统操作

请用简洁、专业的语言回答问题。如果涉及数据查询，请给出具体的搜索建议。"""

        messages = [{"role": "system", "content": system_prompt}]
        
        # 添加数据上下文
        if context_data:
            context_str = "当前数据上下文：\n" + json.dumps(context_data, ensure_ascii=False, indent=2)
            messages.append({"role": "system", "content": context_str})
        
        # 添加历史对话
        if history:
            messages.extend(history[-10:])  # 最多保留10轮对话
        
        # 添加用户消息
        messages.append({"role": "user", "content": message})
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            reply = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if response.usage else None
            
            # 提取搜索关键词建议
            search_keywords = self._extract_search_suggestions(message, reply)
            
            # 生成操作建议
            suggestions = self._generate_suggestions(message, reply)
            
            return {
                "message": reply,
                "tokens_used": tokens_used,
                "model": self.model,
                "search_keywords": search_keywords,
                "suggestions": suggestions
            }
            
        except Exception as e:
            logger.error(f"AI对话失败: {e}")
            return {
                "message": "抱歉，AI服务暂时不可用，请稍后再试。",
                "error": str(e)
            }
    
    def _extract_search_suggestions(self, question: str, answer: str) -> List[str]:
        """从对话中提取搜索建议"""
        import re
        
        keywords = []
        
        # 提取引号中的内容
        quoted = re.findall(r'[「"\'](.*?)[」"\']', answer)
        keywords.extend(quoted[:3])
        
        # 提取地名
        regions = re.findall(r'([^\s]+(?:省|市|县|区))', question + answer)
        keywords.extend(regions[:2])
        
        return list(set(keywords))[:5]
    
    def _generate_suggestions(self, question: str, answer: str) -> List[str]:
        """生成操作建议"""
        suggestions = []
        
        keywords = {
            "查询": "您可以尝试使用智能搜索功能",
            "分析": "建议使用数据分析功能生成报表",
            "比较": "可以使用对比分析功能",
            "趋势": "推荐查看趋势分析图表",
            "导出": "支持导出为Excel或CSV格式",
            "统计": "可以使用汇总分析功能"
        }
        
        for keyword, suggestion in keywords.items():
            if keyword in question or keyword in answer:
                suggestions.append(suggestion)
        
        return suggestions[:3]
    
    async def analyze_query_intent(self, query: str) -> Dict[str, Any]:
        """分析查询意图"""
        
        prompt = f"""分析以下用户查询的意图：
"{query}"

请返回JSON格式，包含：
- intent: 意图类型（search/analyze/compare/export/help/other）
- entities: 识别的实体（地区、年份、类别等）
- suggested_filters: 建议的搜索筛选条件
- suggested_actions: 建议的操作列表"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"意图分析失败: {e}")
            return {
                "intent": "other",
                "entities": {},
                "suggested_filters": {},
                "suggested_actions": []
            }
    
    async def generate_report(
        self, 
        data: List[Dict[str, Any]], 
        report_type: str = "summary"
    ) -> str:
        """生成数据报告"""
        
        prompts = {
            "summary": "请为以下数据生成一份简要的汇总报告，包括主要发现和关键数据点：",
            "detailed": "请为以下数据生成一份详细的分析报告，包括数据特征、趋势分析和建议：",
            "comparison": "请对以下数据进行对比分析，找出差异和共同点：",
            "trend": "请分析以下数据的趋势变化，并预测可能的发展方向："
        }
        
        prompt = prompts.get(report_type, prompts["summary"])
        data_str = json.dumps(data, ensure_ascii=False, indent=2)
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system", 
                        "content": "你是一个专业的数据分析师，擅长生成清晰、专业的数据报告。"
                    },
                    {"role": "user", "content": f"{prompt}\n\n{data_str}"}
                ],
                temperature=0.5,
                max_tokens=2000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"报告生成失败: {e}")
            return f"报告生成失败：{str(e)}"
    
    async def suggest_visualization(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """建议可视化方式"""
        
        prompt = f"""根据以下数据结构，推荐最合适的可视化方式：
{json.dumps(data[:3], ensure_ascii=False)}

请返回JSON格式，包含：
- chart_type: 推荐的图表类型
- x_field: X轴字段
- y_field: Y轴字段
- group_field: 分组字段（可选）
- reason: 推荐理由"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300,
                response_format={"type": "json_object"}
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"可视化建议失败: {e}")
            return {
                "chart_type": "bar",
                "x_field": "region_city",
                "y_field": "income",
                "reason": "默认推荐柱状图展示地区收入对比"
            }
