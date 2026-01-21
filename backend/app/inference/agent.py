# 地方志数据智能管理系统 - 智能Agent
"""工具使用、任务规划、ReAct推理框架"""

import asyncio
import json
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import structlog

from .engine import InferenceEngine, InferenceConfig, InferenceResult

logger = structlog.get_logger()


class ToolType(str, Enum):
    """工具类型"""
    SEARCH = "search"           # 搜索
    RETRIEVE = "retrieve"       # 检索
    CALCULATE = "calculate"     # 计算
    DATABASE = "database"       # 数据库
    API = "api"                 # API调用
    FILE = "file"               # 文件操作
    CUSTOM = "custom"           # 自定义


@dataclass
class ToolParameter:
    """工具参数"""
    name: str
    type: str  # string/number/boolean/array/object
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[str]] = None


@dataclass
class Tool:
    """工具定义"""
    name: str
    description: str
    tool_type: ToolType
    parameters: List[ToolParameter]
    handler: Callable
    examples: List[Dict[str, Any]] = field(default_factory=list)
    requires_confirmation: bool = False
    timeout: float = 30.0
    
    def to_schema(self) -> Dict:
        """转换为函数调用schema"""
        properties = {}
        required = []
        
        for param in self.parameters:
            prop = {
                "type": param.type,
                "description": param.description
            }
            if param.enum:
                prop["enum"] = param.enum
            properties[param.name] = prop
            
            if param.required:
                required.append(param.name)
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }


@dataclass
class ToolCall:
    """工具调用"""
    tool_name: str
    arguments: Dict[str, Any]
    call_id: str = ""
    
    def __post_init__(self):
        if not self.call_id:
            self.call_id = f"call_{int(time.time()*1000)}"


@dataclass
class ToolResult:
    """工具结果"""
    call_id: str
    tool_name: str
    success: bool
    result: Any
    error: Optional[str] = None
    execution_time_ms: float = 0.0


class AgentState(str, Enum):
    """Agent状态"""
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    OBSERVING = "observing"
    FINISHED = "finished"
    ERROR = "error"


@dataclass
class ThoughtStep:
    """思考步骤"""
    step_number: int
    thought: str
    action: Optional[str] = None
    action_input: Optional[Dict] = None
    observation: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now()


@dataclass
class AgentConfig:
    """Agent配置"""
    max_iterations: int = 10
    max_tokens_per_step: int = 1000
    temperature: float = 0.3
    enable_reflection: bool = True
    enable_planning: bool = True
    verbose: bool = False
    timeout_seconds: float = 300.0


@dataclass
class AgentResult:
    """Agent结果"""
    answer: str
    steps: List[ThoughtStep]
    tool_calls: List[ToolCall]
    total_tokens: int = 0
    execution_time_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None


class ToolRegistry:
    """工具注册表"""
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
    
    def register(self, tool: Tool):
        """注册工具"""
        self._tools[tool.name] = tool
        logger.info("Tool registered", name=tool.name)
    
    def unregister(self, name: str):
        """注销工具"""
        self._tools.pop(name, None)
    
    def get(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self._tools.get(name)
    
    def list_tools(self) -> List[Tool]:
        """列出所有工具"""
        return list(self._tools.values())
    
    def get_schemas(self) -> List[Dict]:
        """获取所有工具schema"""
        return [tool.to_schema() for tool in self._tools.values()]
    
    def get_tool_descriptions(self) -> str:
        """获取工具描述文本"""
        descriptions = []
        for tool in self._tools.values():
            params = ", ".join([
                f"{p.name}: {p.type}" + ("" if p.required else " (optional)")
                for p in tool.parameters
            ])
            descriptions.append(f"- {tool.name}({params}): {tool.description}")
        return "\n".join(descriptions)


class ReActAgent:
    """ReAct推理Agent"""
    
    REACT_PROMPT = """你是一个智能助手，可以使用以下工具来回答问题。

可用工具：
{tools}

使用以下格式回答：

Thought: 思考当前需要做什么
Action: 工具名称
Action Input: {{"param1": "value1", "param2": "value2"}}
Observation: 工具返回的结果
... (可以重复Thought/Action/Action Input/Observation多次)
Thought: 我现在知道答案了
Final Answer: 最终答案

注意：
1. 每次只能调用一个工具
2. Action Input必须是有效的JSON格式
3. 如果不需要工具，直接给出Final Answer
4. 仔细分析工具返回的Observation

问题：{question}

{history}"""
    
    def __init__(
        self,
        inference_engine: InferenceEngine,
        config: AgentConfig = None
    ):
        self.engine = inference_engine
        self.config = config or AgentConfig()
        self.tools = ToolRegistry()
        self._state = AgentState.IDLE
    
    def register_tool(self, tool: Tool):
        """注册工具"""
        self.tools.register(tool)
    
    async def execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """执行工具"""
        start_time = time.time()
        tool = self.tools.get(tool_call.tool_name)
        
        if not tool:
            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                success=False,
                result=None,
                error=f"Tool not found: {tool_call.tool_name}"
            )
        
        try:
            # 执行工具
            if asyncio.iscoroutinefunction(tool.handler):
                result = await asyncio.wait_for(
                    tool.handler(**tool_call.arguments),
                    timeout=tool.timeout
                )
            else:
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: tool.handler(**tool_call.arguments)),
                    timeout=tool.timeout
                )
            
            execution_time = (time.time() - start_time) * 1000
            
            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                success=True,
                result=result,
                execution_time_ms=execution_time
            )
            
        except asyncio.TimeoutError:
            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                success=False,
                result=None,
                error=f"Tool execution timeout after {tool.timeout}s"
            )
        except Exception as e:
            return ToolResult(
                call_id=tool_call.call_id,
                tool_name=tool_call.tool_name,
                success=False,
                result=None,
                error=str(e)
            )
    
    def _parse_action(self, text: str) -> Tuple[Optional[str], Optional[Dict]]:
        """解析Action和Action Input"""
        action_match = re.search(r'Action:\s*(.+?)(?:\n|$)', text)
        input_match = re.search(r'Action Input:\s*(\{.*?\})', text, re.DOTALL)
        
        action = action_match.group(1).strip() if action_match else None
        action_input = None
        
        if input_match:
            try:
                action_input = json.loads(input_match.group(1))
            except json.JSONDecodeError:
                # 尝试修复常见的JSON问题
                try:
                    fixed = input_match.group(1).replace("'", '"')
                    action_input = json.loads(fixed)
                except:
                    action_input = {}
        
        return action, action_input
    
    def _parse_final_answer(self, text: str) -> Optional[str]:
        """解析最终答案"""
        match = re.search(r'Final Answer:\s*(.+?)(?:\n\n|$)', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None
    
    async def run(
        self,
        question: str,
        context: Optional[str] = None
    ) -> AgentResult:
        """运行Agent"""
        start_time = time.time()
        steps: List[ThoughtStep] = []
        tool_calls: List[ToolCall] = []
        total_tokens = 0
        history = ""
        
        self._state = AgentState.THINKING
        
        for iteration in range(self.config.max_iterations):
            # 构建提示
            prompt = self.REACT_PROMPT.format(
                tools=self.tools.get_tool_descriptions(),
                question=question,
                history=history
            )
            
            if context:
                prompt = f"背景信息：\n{context}\n\n{prompt}"
            
            # 生成思考
            try:
                result = await self.engine.generate(
                    prompt,
                    max_tokens=self.config.max_tokens_per_step,
                    temperature=self.config.temperature
                )
                total_tokens += result.tokens_used
            except Exception as e:
                self._state = AgentState.ERROR
                return AgentResult(
                    answer="",
                    steps=steps,
                    tool_calls=tool_calls,
                    total_tokens=total_tokens,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    success=False,
                    error=str(e)
                )
            
            response_text = result.content
            
            # 检查是否有最终答案
            final_answer = self._parse_final_answer(response_text)
            if final_answer:
                step = ThoughtStep(
                    step_number=len(steps) + 1,
                    thought=response_text.split("Final Answer:")[0].replace("Thought:", "").strip(),
                )
                steps.append(step)
                
                self._state = AgentState.FINISHED
                return AgentResult(
                    answer=final_answer,
                    steps=steps,
                    tool_calls=tool_calls,
                    total_tokens=total_tokens,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    success=True
                )
            
            # 解析Action
            action, action_input = self._parse_action(response_text)
            
            if action and action_input is not None:
                self._state = AgentState.ACTING
                
                # 创建工具调用
                tool_call = ToolCall(
                    tool_name=action,
                    arguments=action_input
                )
                tool_calls.append(tool_call)
                
                # 执行工具
                tool_result = await self.execute_tool(tool_call)
                
                self._state = AgentState.OBSERVING
                
                # 格式化观察结果
                if tool_result.success:
                    observation = str(tool_result.result)
                else:
                    observation = f"Error: {tool_result.error}"
                
                # 记录步骤
                thought_match = re.search(r'Thought:\s*(.+?)(?:Action:|$)', response_text, re.DOTALL)
                step = ThoughtStep(
                    step_number=len(steps) + 1,
                    thought=thought_match.group(1).strip() if thought_match else "",
                    action=action,
                    action_input=action_input,
                    observation=observation
                )
                steps.append(step)
                
                # 更新历史
                history += f"\nThought: {step.thought}\nAction: {action}\nAction Input: {json.dumps(action_input, ensure_ascii=False)}\nObservation: {observation}\n"
                
            else:
                # 无法解析，可能是直接回答
                self._state = AgentState.FINISHED
                return AgentResult(
                    answer=response_text,
                    steps=steps,
                    tool_calls=tool_calls,
                    total_tokens=total_tokens,
                    execution_time_ms=(time.time() - start_time) * 1000,
                    success=True
                )
        
        # 达到最大迭代
        self._state = AgentState.FINISHED
        return AgentResult(
            answer="抱歉，我无法在有限步骤内完成这个任务。",
            steps=steps,
            tool_calls=tool_calls,
            total_tokens=total_tokens,
            execution_time_ms=(time.time() - start_time) * 1000,
            success=False,
            error="Max iterations reached"
        )
    
    @property
    def state(self) -> AgentState:
        return self._state


class PlanningAgent:
    """规划型Agent"""
    
    PLANNING_PROMPT = """你是一个任务规划专家。请分析用户的问题，制定一个分步骤的执行计划。

可用工具：
{tools}

请以JSON格式输出计划，格式如下：
{{
    "goal": "最终目标",
    "steps": [
        {{
            "step_id": 1,
            "description": "步骤描述",
            "tool": "工具名称或null",
            "tool_input": {{}},
            "depends_on": []
        }}
    ],
    "expected_outcome": "预期结果"
}}

用户问题：{question}

请制定计划："""
    
    def __init__(
        self,
        inference_engine: InferenceEngine,
        config: AgentConfig = None
    ):
        self.engine = inference_engine
        self.config = config or AgentConfig()
        self.tools = ToolRegistry()
        self.react_agent = ReActAgent(inference_engine, config)
    
    def register_tool(self, tool: Tool):
        """注册工具"""
        self.tools.register(tool)
        self.react_agent.register_tool(tool)
    
    async def plan(self, question: str) -> Dict[str, Any]:
        """制定计划"""
        prompt = self.PLANNING_PROMPT.format(
            tools=self.tools.get_tool_descriptions(),
            question=question
        )
        
        result = await self.engine.generate(
            prompt,
            max_tokens=1000,
            temperature=0.3
        )
        
        # 解析JSON计划
        try:
            # 提取JSON部分
            json_match = re.search(r'\{[\s\S]*\}', result.content)
            if json_match:
                plan = json.loads(json_match.group())
                return plan
        except json.JSONDecodeError:
            pass
        
        # 解析失败，返回简单计划
        return {
            "goal": question,
            "steps": [{"step_id": 1, "description": "直接回答问题", "tool": None}],
            "expected_outcome": "回答用户问题"
        }
    
    async def execute_plan(
        self,
        plan: Dict[str, Any],
        context: Optional[str] = None
    ) -> AgentResult:
        """执行计划"""
        all_steps = []
        all_tool_calls = []
        total_tokens = 0
        results = []
        start_time = time.time()
        
        for step in plan.get("steps", []):
            step_desc = step.get("description", "")
            tool_name = step.get("tool")
            tool_input = step.get("tool_input", {})
            
            if tool_name and self.tools.get(tool_name):
                # 执行工具
                tool_call = ToolCall(
                    tool_name=tool_name,
                    arguments=tool_input
                )
                all_tool_calls.append(tool_call)
                
                tool_result = await self.react_agent.execute_tool(tool_call)
                
                thought_step = ThoughtStep(
                    step_number=len(all_steps) + 1,
                    thought=step_desc,
                    action=tool_name,
                    action_input=tool_input,
                    observation=str(tool_result.result) if tool_result.success else tool_result.error
                )
                all_steps.append(thought_step)
                results.append(tool_result.result if tool_result.success else None)
            else:
                # 使用ReAct处理
                sub_result = await self.react_agent.run(step_desc, context)
                all_steps.extend(sub_result.steps)
                all_tool_calls.extend(sub_result.tool_calls)
                total_tokens += sub_result.total_tokens
                results.append(sub_result.answer)
        
        # 汇总结果
        summary_prompt = f"""根据以下执行结果，总结回答用户的问题。

目标：{plan.get('goal', '')}

执行结果：
{chr(10).join([f'{i+1}. {r}' for i, r in enumerate(results) if r])}

请给出最终答案："""
        
        final_result = await self.engine.generate(
            summary_prompt,
            max_tokens=500,
            temperature=0.3
        )
        total_tokens += final_result.tokens_used
        
        return AgentResult(
            answer=final_result.content,
            steps=all_steps,
            tool_calls=all_tool_calls,
            total_tokens=total_tokens,
            execution_time_ms=(time.time() - start_time) * 1000,
            success=True
        )
    
    async def run(
        self,
        question: str,
        context: Optional[str] = None
    ) -> AgentResult:
        """运行规划Agent"""
        if not self.config.enable_planning:
            return await self.react_agent.run(question, context)
        
        # 制定计划
        plan = await self.plan(question)
        
        # 执行计划
        return await self.execute_plan(plan, context)


# 内置工具

def create_search_tool(search_fn: Callable) -> Tool:
    """创建搜索工具"""
    return Tool(
        name="search",
        description="搜索地方志资料库，查找相关文档",
        tool_type=ToolType.SEARCH,
        parameters=[
            ToolParameter(
                name="query",
                type="string",
                description="搜索关键词"
            ),
            ToolParameter(
                name="top_k",
                type="number",
                description="返回结果数量",
                required=False,
                default=5
            )
        ],
        handler=search_fn
    )


def create_calculate_tool() -> Tool:
    """创建计算工具"""
    def calculate(expression: str) -> str:
        try:
            # 安全计算
            allowed_chars = set("0123456789+-*/().% ")
            if not all(c in allowed_chars for c in expression):
                return "不支持的表达式"
            result = eval(expression)
            return str(result)
        except Exception as e:
            return f"计算错误: {str(e)}"
    
    return Tool(
        name="calculate",
        description="执行数学计算",
        tool_type=ToolType.CALCULATE,
        parameters=[
            ToolParameter(
                name="expression",
                type="string",
                description="数学表达式，如 '2 + 3 * 4'"
            )
        ],
        handler=calculate
    )


def create_date_tool() -> Tool:
    """创建日期工具"""
    def get_date_info(query: str = "today") -> str:
        from datetime import datetime, timedelta
        
        now = datetime.now()
        
        if query == "today":
            return now.strftime("%Y年%m月%d日 %A")
        elif query == "year":
            return str(now.year)
        elif query == "month":
            return str(now.month)
        elif query == "weekday":
            weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
            return weekdays[now.weekday()]
        else:
            return now.strftime("%Y-%m-%d %H:%M:%S")
    
    return Tool(
        name="get_date",
        description="获取当前日期时间信息",
        tool_type=ToolType.CUSTOM,
        parameters=[
            ToolParameter(
                name="query",
                type="string",
                description="查询类型: today/year/month/weekday",
                required=False,
                default="today"
            )
        ],
        handler=get_date_info
    )


class ChroniclesAgent:
    """地方志专用Agent"""
    
    def __init__(
        self,
        inference_engine: InferenceEngine,
        rag_pipeline = None,
        config: AgentConfig = None
    ):
        self.engine = inference_engine
        self.rag = rag_pipeline
        self.config = config or AgentConfig()
        self.agent = PlanningAgent(inference_engine, config)
        
        # 注册内置工具
        self.agent.register_tool(create_calculate_tool())
        self.agent.register_tool(create_date_tool())
        
        # 如果有RAG，注册搜索工具
        if self.rag:
            self.agent.register_tool(self._create_rag_search_tool())
    
    def _create_rag_search_tool(self) -> Tool:
        """创建RAG搜索工具"""
        async def rag_search(query: str, top_k: int = 5) -> str:
            if not self.rag:
                return "搜索服务不可用"
            
            try:
                results = await self.rag.retrieve(query)
                if not results.chunks:
                    return "未找到相关资料"
                
                output = []
                for i, chunk in enumerate(results.chunks[:top_k]):
                    source = chunk.metadata.get('title', chunk.id)
                    output.append(f"[{i+1}] {source}:\n{chunk.content[:300]}...")
                
                return "\n\n".join(output)
            except Exception as e:
                return f"搜索出错: {str(e)}"
        
        return Tool(
            name="search_chronicles",
            description="搜索地方志资料库，查找历史文献、人物、事件等信息",
            tool_type=ToolType.SEARCH,
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="搜索关键词，如人名、地名、事件等"
                ),
                ToolParameter(
                    name="top_k",
                    type="number",
                    description="返回结果数量",
                    required=False,
                    default=5
                )
            ],
            handler=rag_search
        )
    
    def register_tool(self, tool: Tool):
        """注册自定义工具"""
        self.agent.register_tool(tool)
    
    async def chat(
        self,
        question: str,
        history: Optional[List[Dict[str, str]]] = None
    ) -> AgentResult:
        """对话"""
        # 构建上下文
        context = None
        if history:
            context = "\n".join([
                f"{'用户' if m['role']=='user' else '助手'}: {m['content']}"
                for m in history[-6:]  # 最近6轮
            ])
        
        return await self.agent.run(question, context)
    
    async def analyze(self, topic: str) -> AgentResult:
        """分析主题"""
        question = f"请详细分析以下主题，包括历史背景、发展变化、重要事件和人物：{topic}"
        return await self.agent.run(question)
    
    async def compare(self, items: List[str]) -> AgentResult:
        """比较分析"""
        question = f"请比较分析以下内容的异同点：{', '.join(items)}"
        return await self.agent.run(question)
