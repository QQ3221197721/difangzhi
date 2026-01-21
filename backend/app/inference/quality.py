# 地方志数据智能管理系统 - 质量保障
"""幻觉检测、答案验证、引用追踪、可信度评估"""

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import structlog

from .engine import InferenceEngine, InferenceResult

logger = structlog.get_logger()


class QualityLevel(str, Enum):
    """质量等级"""
    HIGH = "high"           # 高质量
    MEDIUM = "medium"       # 中等质量
    LOW = "low"             # 低质量
    UNRELIABLE = "unreliable"  # 不可靠


class HallucinationType(str, Enum):
    """幻觉类型"""
    FACTUAL = "factual"           # 事实性错误
    FABRICATION = "fabrication"   # 凭空捏造
    CONTRADICTION = "contradiction"  # 自相矛盾
    UNSUPPORTED = "unsupported"   # 无依据断言
    EXAGGERATION = "exaggeration"  # 夸大事实


@dataclass
class Citation:
    """引用"""
    index: int
    source_id: str
    source_title: str
    quoted_text: str
    context_text: str
    confidence: float
    page_or_section: str = ""
    verified: bool = False


@dataclass
class HallucinationReport:
    """幻觉检测报告"""
    detected: bool
    hallucination_type: Optional[HallucinationType] = None
    severity: float = 0.0  # 0-1
    problematic_claims: List[str] = field(default_factory=list)
    explanation: str = ""
    suggestions: List[str] = field(default_factory=list)


@dataclass
class VerificationResult:
    """验证结果"""
    claim: str
    verified: bool
    confidence: float
    supporting_evidence: List[str] = field(default_factory=list)
    contradicting_evidence: List[str] = field(default_factory=list)
    source_ids: List[str] = field(default_factory=list)


@dataclass
class QualityReport:
    """质量报告"""
    quality_level: QualityLevel
    overall_score: float  # 0-100
    factual_accuracy: float
    citation_coverage: float
    coherence_score: float
    completeness_score: float
    hallucination_report: Optional[HallucinationReport] = None
    citations: List[Citation] = field(default_factory=list)
    verifications: List[VerificationResult] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    timestamp: datetime = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            "quality_level": self.quality_level.value,
            "overall_score": round(self.overall_score, 2),
            "factual_accuracy": round(self.factual_accuracy, 2),
            "citation_coverage": round(self.citation_coverage, 2),
            "coherence_score": round(self.coherence_score, 2),
            "completeness_score": round(self.completeness_score, 2),
            "hallucination_detected": self.hallucination_report.detected if self.hallucination_report else False,
            "citation_count": len(self.citations),
            "warnings": self.warnings,
            "suggestions": self.suggestions
        }


class ClaimExtractor:
    """声明提取器"""
    
    def __init__(self, inference_engine: InferenceEngine):
        self.engine = inference_engine
    
    async def extract_claims(self, text: str) -> List[str]:
        """从文本中提取事实性声明"""
        prompt = f"""请从以下文本中提取所有事实性声明（可验证的陈述）。
每行输出一个声明，不要编号。只提取具体的事实陈述，忽略观点和推测。

文本：
{text}

事实性声明："""
        
        try:
            result = await self.engine.generate(prompt, max_tokens=500, temperature=0)
            claims = [c.strip() for c in result.content.strip().split('\n') if c.strip()]
            return claims
        except Exception as e:
            logger.error("Claim extraction failed", error=str(e))
            return []
    
    def extract_claims_simple(self, text: str) -> List[str]:
        """简单规则提取声明"""
        claims = []
        sentences = re.split(r'[。！？.!?]', text)
        
        # 事实性声明的关键词
        fact_indicators = [
            '是', '为', '有', '达', '共', '建于', '位于', '创建于',
            '发生', '出生', '成立', '始建', '距今', '历时'
        ]
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:
                continue
            
            # 检查是否包含事实性指示词
            if any(ind in sentence for ind in fact_indicators):
                # 排除问句和假设句
                if not any(q in sentence for q in ['吗', '呢', '如果', '假设', '可能']):
                    claims.append(sentence)
        
        return claims[:10]  # 限制数量


class HallucinationDetector:
    """幻觉检测器"""
    
    def __init__(self, inference_engine: InferenceEngine):
        self.engine = inference_engine
    
    async def detect(
        self,
        answer: str,
        context: str,
        question: str
    ) -> HallucinationReport:
        """检测回答中的幻觉"""
        prompt = f"""请分析以下AI回答是否存在幻觉（hallucination）问题。

参考资料（可靠来源）：
{context[:2000]}

用户问题：{question}

AI回答：
{answer}

请检查：
1. 回答中是否有无法从参考资料中找到依据的内容？
2. 是否有与参考资料矛盾的内容？
3. 是否有凭空捏造的数据或事实？

请以JSON格式回答：
{{
    "has_hallucination": true/false,
    "hallucination_type": "factual/fabrication/contradiction/unsupported/exaggeration/none",
    "severity": 0-1之间的数字,
    "problematic_claims": ["问题声明1", "问题声明2"],
    "explanation": "具体说明",
    "suggestions": ["改进建议"]
}}"""
        
        try:
            result = await self.engine.generate(prompt, max_tokens=500, temperature=0)
            
            # 解析JSON
            import json
            json_match = re.search(r'\{[\s\S]*\}', result.content)
            if json_match:
                data = json.loads(json_match.group())
                
                hall_type = None
                if data.get("hallucination_type") and data["hallucination_type"] != "none":
                    try:
                        hall_type = HallucinationType(data["hallucination_type"])
                    except ValueError:
                        hall_type = HallucinationType.UNSUPPORTED
                
                return HallucinationReport(
                    detected=data.get("has_hallucination", False),
                    hallucination_type=hall_type,
                    severity=float(data.get("severity", 0)),
                    problematic_claims=data.get("problematic_claims", []),
                    explanation=data.get("explanation", ""),
                    suggestions=data.get("suggestions", [])
                )
        except Exception as e:
            logger.error("Hallucination detection failed", error=str(e))
        
        return HallucinationReport(detected=False)
    
    def detect_simple(
        self,
        answer: str,
        context: str
    ) -> HallucinationReport:
        """简单规则检测"""
        problems = []
        
        # 检查数字
        answer_numbers = set(re.findall(r'\d+', answer))
        context_numbers = set(re.findall(r'\d+', context))
        
        # 回答中有但上下文中没有的数字可能是幻觉
        suspicious_numbers = answer_numbers - context_numbers - {'1', '2', '3', '4', '5', '6', '7', '8', '9', '10'}
        if suspicious_numbers:
            problems.append(f"可疑数字: {suspicious_numbers}")
        
        # 检查专有名词
        # 简单检查：提取可能的专有名词（连续中文字符）
        answer_entities = set(re.findall(r'《[^》]+》|"[^"]+"', answer))
        context_entities = set(re.findall(r'《[^》]+》|"[^"]+"', context))
        
        suspicious_entities = answer_entities - context_entities
        if suspicious_entities:
            problems.append(f"未找到来源的引用: {suspicious_entities}")
        
        detected = len(problems) > 0
        
        return HallucinationReport(
            detected=detected,
            hallucination_type=HallucinationType.UNSUPPORTED if detected else None,
            severity=min(len(problems) * 0.3, 1.0),
            problematic_claims=problems,
            explanation="基于规则检测发现可疑内容" if detected else "",
            suggestions=["建议核实以上内容的来源"] if detected else []
        )


class AnswerVerifier:
    """答案验证器"""
    
    def __init__(self, inference_engine: InferenceEngine):
        self.engine = inference_engine
        self.claim_extractor = ClaimExtractor(inference_engine)
    
    async def verify_claim(
        self,
        claim: str,
        sources: List[Dict[str, Any]]
    ) -> VerificationResult:
        """验证单个声明"""
        # 构建来源文本
        source_texts = []
        source_ids = []
        for src in sources:
            source_texts.append(f"[{src.get('id', '')}] {src.get('content', '')[:500]}")
            source_ids.append(src.get('id', ''))
        
        sources_text = "\n\n".join(source_texts)
        
        prompt = f"""请验证以下声明是否能从给定的资料中得到支持。

声明：{claim}

参考资料：
{sources_text}

请以JSON格式回答：
{{
    "verified": true/false,
    "confidence": 0-1之间的数字,
    "supporting_evidence": ["支持证据1"],
    "contradicting_evidence": ["反对证据1"],
    "source_ids": ["来源ID"]
}}"""
        
        try:
            result = await self.engine.generate(prompt, max_tokens=300, temperature=0)
            
            import json
            json_match = re.search(r'\{[\s\S]*\}', result.content)
            if json_match:
                data = json.loads(json_match.group())
                return VerificationResult(
                    claim=claim,
                    verified=data.get("verified", False),
                    confidence=float(data.get("confidence", 0)),
                    supporting_evidence=data.get("supporting_evidence", []),
                    contradicting_evidence=data.get("contradicting_evidence", []),
                    source_ids=data.get("source_ids", [])
                )
        except Exception as e:
            logger.error("Claim verification failed", claim=claim[:50], error=str(e))
        
        return VerificationResult(
            claim=claim,
            verified=False,
            confidence=0.0
        )
    
    async def verify_answer(
        self,
        answer: str,
        sources: List[Dict[str, Any]],
        max_claims: int = 5
    ) -> List[VerificationResult]:
        """验证整个答案"""
        # 提取声明
        claims = await self.claim_extractor.extract_claims(answer)
        claims = claims[:max_claims]
        
        # 并行验证
        tasks = [self.verify_claim(claim, sources) for claim in claims]
        results = await asyncio.gather(*tasks)
        
        return list(results)


class CitationTracker:
    """引用追踪器"""
    
    def __init__(self):
        pass
    
    def extract_citations(
        self,
        answer: str,
        sources: List[Dict[str, Any]]
    ) -> List[Citation]:
        """从答案中提取引用"""
        citations = []
        
        # 查找引用标记 [来源1], [1], 等
        citation_patterns = [
            r'\[来源(\d+)\]',
            r'\[(\d+)\]',
            r'【(\d+)】',
            r'（(\d+)）'
        ]
        
        for pattern in citation_patterns:
            matches = re.finditer(pattern, answer)
            for match in matches:
                try:
                    idx = int(match.group(1)) - 1
                    if 0 <= idx < len(sources):
                        source = sources[idx]
                        
                        # 提取引用上下文
                        start = max(0, match.start() - 50)
                        end = min(len(answer), match.end() + 50)
                        context_text = answer[start:end]
                        
                        citations.append(Citation(
                            index=idx + 1,
                            source_id=source.get('id', ''),
                            source_title=source.get('title', ''),
                            quoted_text="",
                            context_text=context_text,
                            confidence=0.8,
                            verified=True
                        ))
                except (ValueError, IndexError):
                    pass
        
        return citations
    
    def calculate_coverage(
        self,
        answer: str,
        citations: List[Citation],
        total_sources: int
    ) -> float:
        """计算引用覆盖率"""
        if total_sources == 0:
            return 0.0
        
        # 计算答案中的句子数
        sentences = re.split(r'[。！？.!?]', answer)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        
        if not sentences:
            return 0.0
        
        # 有引用的句子比例
        cited_count = len(citations)
        sentence_count = len(sentences)
        
        # 引用覆盖率 = 引用数 / 句子数（最大为1）
        coverage = min(cited_count / max(sentence_count * 0.5, 1), 1.0)
        
        return coverage


class QualityAssessor:
    """质量评估器"""
    
    def __init__(
        self,
        inference_engine: InferenceEngine,
        enable_llm_verification: bool = True
    ):
        self.engine = inference_engine
        self.enable_llm_verification = enable_llm_verification
        
        self.hallucination_detector = HallucinationDetector(inference_engine)
        self.answer_verifier = AnswerVerifier(inference_engine)
        self.citation_tracker = CitationTracker()
    
    async def assess(
        self,
        answer: str,
        question: str,
        sources: List[Dict[str, Any]],
        context: Optional[str] = None
    ) -> QualityReport:
        """全面评估答案质量"""
        if context is None:
            context = "\n\n".join([
                s.get('content', '')[:500] for s in sources
            ])
        
        # 并行执行各项评估
        tasks = []
        
        # 1. 幻觉检测
        if self.enable_llm_verification:
            tasks.append(self.hallucination_detector.detect(answer, context, question))
        else:
            tasks.append(asyncio.coroutine(lambda: self.hallucination_detector.detect_simple(answer, context))())
        
        # 2. 答案验证
        if self.enable_llm_verification:
            tasks.append(self.answer_verifier.verify_answer(answer, sources))
        else:
            tasks.append(asyncio.coroutine(lambda: [])())
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        hallucination_report = results[0] if not isinstance(results[0], Exception) else HallucinationReport(detected=False)
        verifications = results[1] if not isinstance(results[1], Exception) else []
        
        # 3. 引用追踪
        citations = self.citation_tracker.extract_citations(answer, sources)
        citation_coverage = self.citation_tracker.calculate_coverage(answer, citations, len(sources))
        
        # 4. 计算各项得分
        factual_accuracy = self._calculate_factual_accuracy(verifications, hallucination_report)
        coherence_score = self._calculate_coherence(answer)
        completeness_score = self._calculate_completeness(answer, question)
        
        # 5. 综合得分
        overall_score = self._calculate_overall_score(
            factual_accuracy,
            citation_coverage,
            coherence_score,
            completeness_score,
            hallucination_report
        )
        
        # 6. 确定质量等级
        quality_level = self._determine_quality_level(overall_score, hallucination_report)
        
        # 7. 生成警告和建议
        warnings = self._generate_warnings(hallucination_report, verifications, citations)
        suggestions = self._generate_suggestions(
            factual_accuracy, citation_coverage, coherence_score, completeness_score
        )
        
        return QualityReport(
            quality_level=quality_level,
            overall_score=overall_score,
            factual_accuracy=factual_accuracy,
            citation_coverage=citation_coverage,
            coherence_score=coherence_score,
            completeness_score=completeness_score,
            hallucination_report=hallucination_report,
            citations=citations,
            verifications=verifications,
            warnings=warnings,
            suggestions=suggestions
        )
    
    def _calculate_factual_accuracy(
        self,
        verifications: List[VerificationResult],
        hallucination_report: HallucinationReport
    ) -> float:
        """计算事实准确性得分"""
        if not verifications:
            # 没有验证结果时，根据幻觉检测
            if hallucination_report.detected:
                return 1.0 - hallucination_report.severity
            return 0.8  # 默认分数
        
        verified_count = sum(1 for v in verifications if v.verified)
        base_score = verified_count / len(verifications)
        
        # 如果检测到幻觉，降低分数
        if hallucination_report.detected:
            base_score *= (1.0 - hallucination_report.severity * 0.5)
        
        return min(base_score, 1.0)
    
    def _calculate_coherence(self, answer: str) -> float:
        """计算连贯性得分"""
        # 简单规则：检查答案结构
        score = 0.7  # 基础分
        
        # 有段落结构
        if '\n\n' in answer or len(answer.split('\n')) > 1:
            score += 0.1
        
        # 有连接词
        connectors = ['因此', '所以', '另外', '此外', '然而', '但是', '首先', '其次', '最后', '总之']
        if any(c in answer for c in connectors):
            score += 0.1
        
        # 长度适中
        if 100 < len(answer) < 2000:
            score += 0.1
        
        return min(score, 1.0)
    
    def _calculate_completeness(self, answer: str, question: str) -> float:
        """计算完整性得分"""
        score = 0.6  # 基础分
        
        # 检查是否回答了问题类型
        question_types = {
            '什么': '解释说明',
            '为什么': '原因分析',
            '如何': '方法步骤',
            '多少': '数量信息',
            '何时': '时间信息',
            '哪里': '地点信息',
            '谁': '人物信息'
        }
        
        for q_word, expected in question_types.items():
            if q_word in question:
                # 简单检查是否有相关内容
                if len(answer) > 50:
                    score += 0.2
                break
        
        # 答案长度
        if len(answer) > 200:
            score += 0.1
        if len(answer) > 500:
            score += 0.1
        
        return min(score, 1.0)
    
    def _calculate_overall_score(
        self,
        factual_accuracy: float,
        citation_coverage: float,
        coherence_score: float,
        completeness_score: float,
        hallucination_report: HallucinationReport
    ) -> float:
        """计算综合得分"""
        # 加权平均
        weights = {
            'factual': 0.35,
            'citation': 0.25,
            'coherence': 0.20,
            'completeness': 0.20
        }
        
        score = (
            factual_accuracy * weights['factual'] +
            citation_coverage * weights['citation'] +
            coherence_score * weights['coherence'] +
            completeness_score * weights['completeness']
        )
        
        # 幻觉惩罚
        if hallucination_report.detected:
            penalty = hallucination_report.severity * 0.3
            score = score * (1 - penalty)
        
        return score * 100
    
    def _determine_quality_level(
        self,
        overall_score: float,
        hallucination_report: HallucinationReport
    ) -> QualityLevel:
        """确定质量等级"""
        # 严重幻觉直接判定为不可靠
        if hallucination_report.detected and hallucination_report.severity > 0.7:
            return QualityLevel.UNRELIABLE
        
        if overall_score >= 80:
            return QualityLevel.HIGH
        elif overall_score >= 60:
            return QualityLevel.MEDIUM
        elif overall_score >= 40:
            return QualityLevel.LOW
        else:
            return QualityLevel.UNRELIABLE
    
    def _generate_warnings(
        self,
        hallucination_report: HallucinationReport,
        verifications: List[VerificationResult],
        citations: List[Citation]
    ) -> List[str]:
        """生成警告"""
        warnings = []
        
        if hallucination_report.detected:
            warnings.append(f"检测到可能的幻觉内容: {hallucination_report.explanation}")
            warnings.extend(hallucination_report.problematic_claims)
        
        unverified = [v for v in verifications if not v.verified]
        if unverified:
            warnings.append(f"有 {len(unverified)} 条声明未能验证")
        
        if not citations:
            warnings.append("回答未包含引用标记")
        
        return warnings
    
    def _generate_suggestions(
        self,
        factual_accuracy: float,
        citation_coverage: float,
        coherence_score: float,
        completeness_score: float
    ) -> List[str]:
        """生成改进建议"""
        suggestions = []
        
        if factual_accuracy < 0.7:
            suggestions.append("建议核实事实性内容，确保与原始资料一致")
        
        if citation_coverage < 0.5:
            suggestions.append("建议增加引用标记，标明信息来源")
        
        if coherence_score < 0.7:
            suggestions.append("建议改善答案结构，增加段落划分和过渡")
        
        if completeness_score < 0.7:
            suggestions.append("建议补充更多细节，更全面地回答问题")
        
        return suggestions


class QualityGuard:
    """质量守卫 - 在生成时进行质量控制"""
    
    def __init__(
        self,
        assessor: QualityAssessor,
        min_quality_score: float = 60.0,
        max_retries: int = 2
    ):
        self.assessor = assessor
        self.min_quality_score = min_quality_score
        self.max_retries = max_retries
    
    async def guarded_generate(
        self,
        generate_fn: Callable,
        question: str,
        sources: List[Dict[str, Any]],
        **kwargs
    ) -> Tuple[str, QualityReport]:
        """带质量保障的生成"""
        best_answer = None
        best_report = None
        
        for attempt in range(self.max_retries + 1):
            # 生成答案
            if asyncio.iscoroutinefunction(generate_fn):
                answer = await generate_fn(question, **kwargs)
            else:
                answer = generate_fn(question, **kwargs)
            
            if hasattr(answer, 'content'):
                answer = answer.content
            
            # 评估质量
            report = await self.assessor.assess(
                answer=answer,
                question=question,
                sources=sources
            )
            
            # 记录最佳结果
            if best_report is None or report.overall_score > best_report.overall_score:
                best_answer = answer
                best_report = report
            
            # 质量达标则返回
            if report.overall_score >= self.min_quality_score:
                logger.info(
                    "Quality check passed",
                    score=report.overall_score,
                    attempt=attempt + 1
                )
                return answer, report
            
            logger.warning(
                "Quality check failed, retrying",
                score=report.overall_score,
                attempt=attempt + 1
            )
        
        # 返回最佳结果
        logger.warning(
            "Quality threshold not met after retries",
            best_score=best_report.overall_score
        )
        return best_answer, best_report
