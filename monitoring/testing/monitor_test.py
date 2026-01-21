# 地方志数据智能管理系统 - 监控测试套件
"""监控系统的端到端测试"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum
import httpx
import structlog

logger = structlog.get_logger()


class TestStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WARNING = "warning"


@dataclass
class TestResult:
    """测试结果"""
    name: str
    status: TestStatus
    duration_ms: float
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class MetricValidation:
    """指标验证规则"""
    metric_name: str
    expected_value: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    labels: Dict[str, str] = field(default_factory=dict)


class MetricValidator:
    """Prometheus指标验证器"""
    
    def __init__(self, prometheus_url: str = "http://localhost:9090"):
        self.prometheus_url = prometheus_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def query(self, query: str) -> List[Dict]:
        """执行PromQL查询"""
        try:
            response = await self.client.get(
                f"{self.prometheus_url}/api/v1/query",
                params={"query": query}
            )
            response.raise_for_status()
            data = response.json()
            if data["status"] == "success":
                return data["data"]["result"]
            return []
        except Exception as e:
            logger.error("Prometheus query failed", query=query, error=str(e))
            return []
    
    async def validate_metric(self, validation: MetricValidation) -> TestResult:
        """验证单个指标"""
        start = time.time()
        
        # 构建查询
        query = validation.metric_name
        if validation.labels:
            label_str = ",".join(f'{k}="{v}"' for k, v in validation.labels.items())
            query = f"{validation.metric_name}{{{label_str}}}"
        
        results = await self.query(query)
        duration = (time.time() - start) * 1000
        
        if not results:
            return TestResult(
                name=f"metric_{validation.metric_name}",
                status=TestStatus.FAILED,
                duration_ms=duration,
                message=f"指标 {validation.metric_name} 不存在或无数据"
            )
        
        value = float(results[0]["value"][1])
        
        # 验证值
        if validation.expected_value is not None:
            if abs(value - validation.expected_value) > 0.01:
                return TestResult(
                    name=f"metric_{validation.metric_name}",
                    status=TestStatus.FAILED,
                    duration_ms=duration,
                    message=f"期望值 {validation.expected_value}, 实际值 {value}",
                    details={"actual": value, "expected": validation.expected_value}
                )
        
        if validation.min_value is not None and value < validation.min_value:
            return TestResult(
                name=f"metric_{validation.metric_name}",
                status=TestStatus.FAILED,
                duration_ms=duration,
                message=f"值 {value} 小于最小值 {validation.min_value}",
                details={"actual": value, "min": validation.min_value}
            )
        
        if validation.max_value is not None and value > validation.max_value:
            return TestResult(
                name=f"metric_{validation.metric_name}",
                status=TestStatus.WARNING,
                duration_ms=duration,
                message=f"值 {value} 超过最大值 {validation.max_value}",
                details={"actual": value, "max": validation.max_value}
            )
        
        return TestResult(
            name=f"metric_{validation.metric_name}",
            status=TestStatus.PASSED,
            duration_ms=duration,
            message=f"值 {value} 在预期范围内",
            details={"actual": value}
        )
    
    async def validate_all(self, validations: List[MetricValidation]) -> List[TestResult]:
        """批量验证指标"""
        tasks = [self.validate_metric(v) for v in validations]
        return await asyncio.gather(*tasks)


class AlertTestRunner:
    """告警测试运行器"""
    
    def __init__(
        self,
        alertmanager_url: str = "http://localhost:9093",
        prometheus_url: str = "http://localhost:9090"
    ):
        self.alertmanager_url = alertmanager_url
        self.prometheus_url = prometheus_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def get_active_alerts(self) -> List[Dict]:
        """获取活跃告警"""
        try:
            response = await self.client.get(
                f"{self.alertmanager_url}/api/v2/alerts"
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error("Get alerts failed", error=str(e))
            return []
    
    async def test_alert_firing(self, alert_name: str, timeout: int = 60) -> TestResult:
        """测试告警是否能正确触发"""
        start = time.time()
        
        # 等待告警触发
        for _ in range(timeout):
            alerts = await self.get_active_alerts()
            for alert in alerts:
                if alert.get("labels", {}).get("alertname") == alert_name:
                    duration = (time.time() - start) * 1000
                    return TestResult(
                        name=f"alert_firing_{alert_name}",
                        status=TestStatus.PASSED,
                        duration_ms=duration,
                        message=f"告警 {alert_name} 在 {duration/1000:.1f}s 内触发"
                    )
            await asyncio.sleep(1)
        
        duration = (time.time() - start) * 1000
        return TestResult(
            name=f"alert_firing_{alert_name}",
            status=TestStatus.FAILED,
            duration_ms=duration,
            message=f"告警 {alert_name} 在 {timeout}s 内未触发"
        )
    
    async def test_alert_routing(self, alert_name: str, expected_receiver: str) -> TestResult:
        """测试告警路由"""
        start = time.time()
        alerts = await self.get_active_alerts()
        
        for alert in alerts:
            if alert.get("labels", {}).get("alertname") == alert_name:
                receivers = alert.get("receivers", [])
                receiver_names = [r.get("name") for r in receivers]
                
                duration = (time.time() - start) * 1000
                if expected_receiver in receiver_names:
                    return TestResult(
                        name=f"alert_routing_{alert_name}",
                        status=TestStatus.PASSED,
                        duration_ms=duration,
                        message=f"告警正确路由到 {expected_receiver}"
                    )
                else:
                    return TestResult(
                        name=f"alert_routing_{alert_name}",
                        status=TestStatus.FAILED,
                        duration_ms=duration,
                        message=f"告警未路由到 {expected_receiver}",
                        details={"actual_receivers": receiver_names}
                    )
        
        return TestResult(
            name=f"alert_routing_{alert_name}",
            status=TestStatus.SKIPPED,
            duration_ms=(time.time() - start) * 1000,
            message=f"告警 {alert_name} 未找到"
        )


class DashboardTester:
    """Grafana仪表板测试"""
    
    def __init__(
        self,
        grafana_url: str = "http://localhost:3000",
        api_key: str = ""
    ):
        self.grafana_url = grafana_url
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.client = httpx.AsyncClient(timeout=30.0, headers=self.headers)
    
    async def test_dashboard_exists(self, uid: str) -> TestResult:
        """测试仪表板是否存在"""
        start = time.time()
        try:
            response = await self.client.get(
                f"{self.grafana_url}/api/dashboards/uid/{uid}"
            )
            duration = (time.time() - start) * 1000
            
            if response.status_code == 200:
                data = response.json()
                return TestResult(
                    name=f"dashboard_exists_{uid}",
                    status=TestStatus.PASSED,
                    duration_ms=duration,
                    message=f"仪表板 {data['dashboard']['title']} 存在"
                )
            else:
                return TestResult(
                    name=f"dashboard_exists_{uid}",
                    status=TestStatus.FAILED,
                    duration_ms=duration,
                    message=f"仪表板 {uid} 不存在"
                )
        except Exception as e:
            return TestResult(
                name=f"dashboard_exists_{uid}",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=f"检查仪表板失败: {e}"
            )
    
    async def test_dashboard_panels(self, uid: str, expected_panels: int) -> TestResult:
        """测试仪表板面板数量"""
        start = time.time()
        try:
            response = await self.client.get(
                f"{self.grafana_url}/api/dashboards/uid/{uid}"
            )
            duration = (time.time() - start) * 1000
            
            if response.status_code == 200:
                data = response.json()
                panels = data["dashboard"].get("panels", [])
                actual_count = len(panels)
                
                if actual_count >= expected_panels:
                    return TestResult(
                        name=f"dashboard_panels_{uid}",
                        status=TestStatus.PASSED,
                        duration_ms=duration,
                        message=f"面板数量 {actual_count} >= {expected_panels}"
                    )
                else:
                    return TestResult(
                        name=f"dashboard_panels_{uid}",
                        status=TestStatus.WARNING,
                        duration_ms=duration,
                        message=f"面板数量 {actual_count} < {expected_panels}"
                    )
            return TestResult(
                name=f"dashboard_panels_{uid}",
                status=TestStatus.FAILED,
                duration_ms=duration,
                message=f"获取仪表板失败"
            )
        except Exception as e:
            return TestResult(
                name=f"dashboard_panels_{uid}",
                status=TestStatus.FAILED,
                duration_ms=(time.time() - start) * 1000,
                message=str(e)
            )


class MonitoringTestSuite:
    """监控测试套件"""
    
    def __init__(self, config: Dict[str, str] = None):
        config = config or {}
        self.metric_validator = MetricValidator(
            config.get("prometheus_url", "http://localhost:9090")
        )
        self.alert_runner = AlertTestRunner(
            config.get("alertmanager_url", "http://localhost:9093"),
            config.get("prometheus_url", "http://localhost:9090")
        )
        self.dashboard_tester = DashboardTester(
            config.get("grafana_url", "http://localhost:3000"),
            config.get("grafana_api_key", "")
        )
        self.results: List[TestResult] = []
    
    async def run_all_tests(self) -> List[TestResult]:
        """运行所有监控测试"""
        self.results = []
        
        # 1. 指标存在性测试
        metric_validations = [
            MetricValidation("up", min_value=1),
            MetricValidation("http_requests_total"),
            MetricValidation("http_request_duration_seconds_bucket"),
            MetricValidation("process_cpu_seconds_total"),
            MetricValidation("process_resident_memory_bytes"),
        ]
        metric_results = await self.metric_validator.validate_all(metric_validations)
        self.results.extend(metric_results)
        
        # 2. 仪表板测试
        dashboard_results = [
            await self.dashboard_tester.test_dashboard_exists("lcs-overview"),
            await self.dashboard_tester.test_dashboard_exists("lcs-api-metrics"),
        ]
        self.results.extend(dashboard_results)
        
        return self.results
    
    def get_summary(self) -> Dict[str, Any]:
        """获取测试摘要"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in self.results if r.status == TestStatus.FAILED)
        warnings = sum(1 for r in self.results if r.status == TestStatus.WARNING)
        skipped = sum(1 for r in self.results if r.status == TestStatus.SKIPPED)
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "skipped": skipped,
            "pass_rate": passed / total * 100 if total > 0 else 0,
            "timestamp": datetime.now().isoformat(),
        }
