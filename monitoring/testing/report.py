# 地方志数据智能管理系统 - 监控报告
"""生成监控测试报告"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List
from pathlib import Path
import structlog

logger = structlog.get_logger()


@dataclass
class ReportSection:
    """报告章节"""
    title: str
    content: str
    status: str  # passed/failed/warning
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        self.details = self.details or {}


class MonitoringReport:
    """监控报告生成器"""
    
    def __init__(self, title: str = "监控系统测试报告"):
        self.title = title
        self.sections: List[ReportSection] = []
        self.metadata: Dict[str, Any] = {
            "generated_at": datetime.now().isoformat(),
            "version": "1.0.0"
        }
    
    def add_section(self, section: ReportSection):
        """添加章节"""
        self.sections.append(section)
    
    def add_test_results(self, results: List[Any]):
        """添加测试结果"""
        passed = sum(1 for r in results if r.status.value == "passed")
        failed = sum(1 for r in results if r.status.value == "failed")
        warnings = sum(1 for r in results if r.status.value == "warning")
        
        # 汇总章节
        status = "passed" if failed == 0 else "failed"
        self.add_section(ReportSection(
            title="测试汇总",
            content=f"总计 {len(results)} 个测试: {passed} 通过, {failed} 失败, {warnings} 警告",
            status=status,
            details={
                "total": len(results),
                "passed": passed,
                "failed": failed,
                "warnings": warnings,
                "pass_rate": f"{passed/len(results)*100:.1f}%" if results else "N/A"
            }
        ))
        
        # 详细结果
        for result in results:
            self.add_section(ReportSection(
                title=result.name,
                content=result.message,
                status=result.status.value,
                details={
                    "duration_ms": result.duration_ms,
                    **result.details
                }
            ))
    
    def add_availability_report(self, availability_data: Dict[str, float]):
        """添加可用性报告"""
        content_lines = []
        status = "passed"
        
        for service, availability in availability_data.items():
            content_lines.append(f"- {service}: {availability:.2f}%")
            if availability < 99.0:
                status = "warning"
            if availability < 95.0:
                status = "failed"
        
        self.add_section(ReportSection(
            title="服务可用性",
            content="\n".join(content_lines),
            status=status,
            details=availability_data
        ))
    
    def add_performance_report(self, performance_data: Dict[str, Dict[str, float]]):
        """添加性能报告"""
        content_lines = []
        status = "passed"
        
        for service, metrics in performance_data.items():
            avg_rt = metrics.get("avg_response_time_ms", 0)
            p95_rt = metrics.get("p95_response_time_ms", 0)
            content_lines.append(f"- {service}: 平均 {avg_rt:.0f}ms, P95 {p95_rt:.0f}ms")
            
            if p95_rt > 1000:
                status = "warning"
            if p95_rt > 3000:
                status = "failed"
        
        self.add_section(ReportSection(
            title="性能指标",
            content="\n".join(content_lines),
            status=status,
            details=performance_data
        ))
    
    def to_json(self) -> str:
        """导出为JSON"""
        return json.dumps({
            "title": self.title,
            "metadata": self.metadata,
            "sections": [asdict(s) for s in self.sections]
        }, ensure_ascii=False, indent=2)
    
    def to_html(self) -> str:
        """导出为HTML"""
        status_colors = {
            "passed": "#4CAF50",
            "failed": "#F44336",
            "warning": "#FF9800"
        }
        
        sections_html = ""
        for section in self.sections:
            color = status_colors.get(section.status, "#9E9E9E")
            details_html = ""
            if section.details:
                details_html = "<ul>" + "".join(
                    f"<li><strong>{k}:</strong> {v}</li>"
                    for k, v in section.details.items()
                ) + "</ul>"
            
            sections_html += f"""
            <div class="section" style="border-left: 4px solid {color}; padding-left: 16px; margin: 16px 0;">
                <h3 style="margin: 0;">{section.title} 
                    <span style="color: {color}; font-size: 14px;">({section.status})</span>
                </h3>
                <p>{section.content}</p>
                {details_html}
            </div>
            """
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{self.title}</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif; 
                       max-width: 800px; margin: 0 auto; padding: 20px; }}
                h1 {{ color: #333; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
                .metadata {{ color: #666; font-size: 14px; margin-bottom: 20px; }}
                .section {{ background: #f9f9f9; border-radius: 4px; padding: 12px; }}
                .section h3 {{ color: #333; }}
                .section p {{ color: #555; white-space: pre-wrap; }}
                .section ul {{ margin: 8px 0; padding-left: 20px; }}
            </style>
        </head>
        <body>
            <h1>{self.title}</h1>
            <div class="metadata">
                生成时间: {self.metadata['generated_at']}<br>
                版本: {self.metadata['version']}
            </div>
            {sections_html}
        </body>
        </html>
        """
    
    def to_markdown(self) -> str:
        """导出为Markdown"""
        status_icons = {
            "passed": "✅",
            "failed": "❌",
            "warning": "⚠️"
        }
        
        md = f"# {self.title}\n\n"
        md += f"**生成时间:** {self.metadata['generated_at']}\n\n"
        md += "---\n\n"
        
        for section in self.sections:
            icon = status_icons.get(section.status, "❓")
            md += f"## {icon} {section.title}\n\n"
            md += f"{section.content}\n\n"
            
            if section.details:
                md += "| 指标 | 值 |\n|---|---|\n"
                for k, v in section.details.items():
                    md += f"| {k} | {v} |\n"
                md += "\n"
        
        return md
    
    def save(self, path: str, format: str = "html"):
        """保存报告"""
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if format == "html":
            content = self.to_html()
        elif format == "json":
            content = self.to_json()
        elif format == "md":
            content = self.to_markdown()
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        logger.info("Report saved", path=str(output_path), format=format)
        return output_path
