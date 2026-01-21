"""
安全扫描模块 - 代码扫描、依赖扫描、SAST/DAST
Security Scanning Module - Code Scanning, Dependency Scanning, SAST/DAST
"""

import asyncio
import hashlib
import json
import re
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Callable, Union
import logging

logger = logging.getLogger(__name__)


# ==================== 扫描结果类型 ====================

class SeverityLevel(str, Enum):
    """严重程度"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class VulnerabilityType(str, Enum):
    """漏洞类型"""
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    CSRF = "csrf"
    PATH_TRAVERSAL = "path_traversal"
    COMMAND_INJECTION = "command_injection"
    INSECURE_DESERIALIZATION = "insecure_deserialization"
    SENSITIVE_DATA_EXPOSURE = "sensitive_data_exposure"
    BROKEN_AUTH = "broken_auth"
    SECURITY_MISCONFIGURATION = "security_misconfiguration"
    DEPENDENCY_VULNERABILITY = "dependency_vulnerability"
    HARDCODED_CREDENTIAL = "hardcoded_credential"
    WEAK_CRYPTO = "weak_crypto"
    INSECURE_RANDOM = "insecure_random"
    RACE_CONDITION = "race_condition"
    BUFFER_OVERFLOW = "buffer_overflow"
    XXE = "xxe"
    SSRF = "ssrf"
    OPEN_REDIRECT = "open_redirect"
    OTHER = "other"


@dataclass
class ScanFinding:
    """扫描发现"""
    id: str
    title: str
    description: str
    severity: SeverityLevel
    vulnerability_type: VulnerabilityType
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    cwe_id: Optional[str] = None
    cve_id: Optional[str] = None
    cvss_score: Optional[float] = None
    recommendation: Optional[str] = None
    references: List[str] = field(default_factory=list)
    false_positive: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "vulnerability_type": self.vulnerability_type.value,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "code_snippet": self.code_snippet,
            "cwe_id": self.cwe_id,
            "cve_id": self.cve_id,
            "cvss_score": self.cvss_score,
            "recommendation": self.recommendation,
            "references": self.references,
            "false_positive": self.false_positive,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ScanReport:
    """扫描报告"""
    scan_id: str
    scan_type: str
    target: str
    started_at: datetime
    completed_at: Optional[datetime]
    status: str
    findings: List[ScanFinding]
    summary: Dict[str, int]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "scan_id": self.scan_id,
            "scan_type": self.scan_type,
            "target": self.target,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
            "metadata": self.metadata
        }


# ==================== 扫描器基类 ====================

class SecurityScanner(ABC):
    """安全扫描器基类"""
    
    @abstractmethod
    async def scan(self, target: str, **kwargs) -> ScanReport:
        """执行扫描"""
        pass
    
    def _generate_scan_id(self) -> str:
        """生成扫描ID"""
        return hashlib.md5(
            f"{datetime.now().isoformat()}-{id(self)}".encode()
        ).hexdigest()[:12]
    
    def _create_summary(self, findings: List[ScanFinding]) -> Dict[str, int]:
        """创建摘要"""
        summary = {
            "total": len(findings),
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0
        }
        
        for finding in findings:
            summary[finding.severity.value] += 1
        
        return summary


# ==================== SAST静态分析扫描器 ====================

class SASTScanner(SecurityScanner):
    """静态应用安全测试(SAST)扫描器"""
    
    # Python代码安全规则
    PYTHON_RULES = {
        "sql_injection": {
            "patterns": [
                r"execute\s*\(\s*[\"'].*%[sd].*[\"']\s*%",
                r"execute\s*\(\s*f[\"'].*\{.*\}.*[\"']\s*\)",
                r"cursor\.execute\s*\(\s*[\"'].*\+.*[\"']\s*\)",
                r"\.raw\s*\(\s*[\"'].*%.*[\"']",
            ],
            "severity": SeverityLevel.CRITICAL,
            "cwe": "CWE-89",
            "recommendation": "使用参数化查询而非字符串拼接"
        },
        "command_injection": {
            "patterns": [
                r"os\.system\s*\(",
                r"subprocess\.call\s*\(\s*[^,\]]+\s*,\s*shell\s*=\s*True",
                r"subprocess\.Popen\s*\(\s*[^,\]]+\s*,\s*shell\s*=\s*True",
                r"eval\s*\(",
                r"exec\s*\(",
            ],
            "severity": SeverityLevel.CRITICAL,
            "cwe": "CWE-78",
            "recommendation": "避免使用shell=True，使用列表参数传递命令"
        },
        "path_traversal": {
            "patterns": [
                r"open\s*\(\s*(?:request|user|input|data)\.",
                r"os\.path\.join\s*\(.*(?:request|user|input).*\)",
                r"send_file\s*\(\s*(?:request|user|input)",
            ],
            "severity": SeverityLevel.HIGH,
            "cwe": "CWE-22",
            "recommendation": "验证和清理用户输入的文件路径"
        },
        "hardcoded_credential": {
            "patterns": [
                r"(?i)(password|passwd|pwd|secret|api_key|apikey|token)\s*=\s*[\"'][^\"']{8,}[\"']",
                r"(?i)(password|passwd|pwd|secret|api_key|apikey|token)\s*:\s*[\"'][^\"']{8,}[\"']",
            ],
            "severity": SeverityLevel.HIGH,
            "cwe": "CWE-798",
            "recommendation": "使用环境变量或密钥管理服务存储敏感信息"
        },
        "weak_crypto": {
            "patterns": [
                r"hashlib\.md5\s*\(",
                r"hashlib\.sha1\s*\(",
                r"DES\s*\(",
                r"RC4\s*\(",
            ],
            "severity": SeverityLevel.MEDIUM,
            "cwe": "CWE-327",
            "recommendation": "使用强加密算法如AES-256、SHA-256"
        },
        "insecure_random": {
            "patterns": [
                r"random\.random\s*\(",
                r"random\.randint\s*\(",
                r"random\.choice\s*\(",
            ],
            "severity": SeverityLevel.MEDIUM,
            "cwe": "CWE-330",
            "recommendation": "安全场景使用secrets模块代替random"
        },
        "xss": {
            "patterns": [
                r"Markup\s*\(",
                r"\|safe\b",
                r"mark_safe\s*\(",
                r"dangerouslySetInnerHTML",
            ],
            "severity": SeverityLevel.HIGH,
            "cwe": "CWE-79",
            "recommendation": "对输出进行HTML转义"
        },
        "xxe": {
            "patterns": [
                r"etree\.parse\s*\(",
                r"xml\.dom\.minidom\.parse\s*\(",
                r"XMLParser\s*\(\s*\)",
            ],
            "severity": SeverityLevel.HIGH,
            "cwe": "CWE-611",
            "recommendation": "禁用XML外部实体解析"
        },
        "ssrf": {
            "patterns": [
                r"requests\.get\s*\(\s*(?:request|user|input)",
                r"urllib\.request\.urlopen\s*\(\s*(?:request|user|input)",
                r"httpx\.get\s*\(\s*(?:request|user|input)",
            ],
            "severity": SeverityLevel.HIGH,
            "cwe": "CWE-918",
            "recommendation": "验证和限制可访问的URL"
        },
        "deserialization": {
            "patterns": [
                r"pickle\.loads?\s*\(",
                r"yaml\.load\s*\(\s*[^,]+\s*\)",
                r"marshal\.loads?\s*\(",
            ],
            "severity": SeverityLevel.CRITICAL,
            "cwe": "CWE-502",
            "recommendation": "避免反序列化不可信数据，使用yaml.safe_load"
        },
        "debug_enabled": {
            "patterns": [
                r"DEBUG\s*=\s*True",
                r"app\.run\s*\([^)]*debug\s*=\s*True",
            ],
            "severity": SeverityLevel.MEDIUM,
            "cwe": "CWE-489",
            "recommendation": "生产环境禁用调试模式"
        },
    }
    
    # JavaScript/TypeScript安全规则
    JS_RULES = {
        "xss": {
            "patterns": [
                r"innerHTML\s*=",
                r"outerHTML\s*=",
                r"document\.write\s*\(",
                r"dangerouslySetInnerHTML",
                r"v-html\s*=",
            ],
            "severity": SeverityLevel.HIGH,
            "cwe": "CWE-79",
            "recommendation": "使用textContent或框架的安全绑定"
        },
        "eval": {
            "patterns": [
                r"\beval\s*\(",
                r"new\s+Function\s*\(",
                r"setTimeout\s*\(\s*[\"']",
                r"setInterval\s*\(\s*[\"']",
            ],
            "severity": SeverityLevel.HIGH,
            "cwe": "CWE-95",
            "recommendation": "避免使用eval和动态代码执行"
        },
        "prototype_pollution": {
            "patterns": [
                r"\[.*__proto__.*\]",
                r"\.constructor\s*\[",
                r"Object\.assign\s*\(\s*\{\}",
            ],
            "severity": SeverityLevel.HIGH,
            "cwe": "CWE-1321",
            "recommendation": "验证对象属性名，使用Object.create(null)"
        },
        "hardcoded_secret": {
            "patterns": [
                r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*[\"'][^\"']{8,}[\"']",
            ],
            "severity": SeverityLevel.HIGH,
            "cwe": "CWE-798",
            "recommendation": "使用环境变量存储敏感信息"
        },
        "open_redirect": {
            "patterns": [
                r"window\.location\s*=\s*(?:req|params|query)",
                r"location\.href\s*=\s*(?:req|params|query)",
            ],
            "severity": SeverityLevel.MEDIUM,
            "cwe": "CWE-601",
            "recommendation": "验证重定向URL白名单"
        },
    }
    
    def __init__(self):
        self.compiled_rules: Dict[str, Dict] = {}
        self._compile_rules()
    
    def _compile_rules(self):
        """编译正则规则"""
        for name, rule in self.PYTHON_RULES.items():
            self.compiled_rules[f"python:{name}"] = {
                "patterns": [re.compile(p, re.IGNORECASE) for p in rule["patterns"]],
                "severity": rule["severity"],
                "cwe": rule["cwe"],
                "recommendation": rule["recommendation"],
                "vuln_type": self._get_vuln_type(name)
            }
        
        for name, rule in self.JS_RULES.items():
            self.compiled_rules[f"js:{name}"] = {
                "patterns": [re.compile(p, re.IGNORECASE) for p in rule["patterns"]],
                "severity": rule["severity"],
                "cwe": rule["cwe"],
                "recommendation": rule["recommendation"],
                "vuln_type": self._get_vuln_type(name)
            }
    
    def _get_vuln_type(self, name: str) -> VulnerabilityType:
        """获取漏洞类型"""
        mapping = {
            "sql_injection": VulnerabilityType.SQL_INJECTION,
            "command_injection": VulnerabilityType.COMMAND_INJECTION,
            "path_traversal": VulnerabilityType.PATH_TRAVERSAL,
            "hardcoded_credential": VulnerabilityType.HARDCODED_CREDENTIAL,
            "hardcoded_secret": VulnerabilityType.HARDCODED_CREDENTIAL,
            "weak_crypto": VulnerabilityType.WEAK_CRYPTO,
            "insecure_random": VulnerabilityType.INSECURE_RANDOM,
            "xss": VulnerabilityType.XSS,
            "xxe": VulnerabilityType.XXE,
            "ssrf": VulnerabilityType.SSRF,
            "deserialization": VulnerabilityType.INSECURE_DESERIALIZATION,
            "eval": VulnerabilityType.COMMAND_INJECTION,
            "prototype_pollution": VulnerabilityType.OTHER,
            "open_redirect": VulnerabilityType.OPEN_REDIRECT,
            "debug_enabled": VulnerabilityType.SECURITY_MISCONFIGURATION,
        }
        return mapping.get(name, VulnerabilityType.OTHER)
    
    async def scan(self, target: str, **kwargs) -> ScanReport:
        """扫描目标路径"""
        scan_id = self._generate_scan_id()
        started_at = datetime.now()
        findings = []
        
        target_path = Path(target)
        
        if target_path.is_file():
            findings.extend(await self._scan_file(target_path))
        elif target_path.is_dir():
            findings.extend(await self._scan_directory(target_path))
        
        return ScanReport(
            scan_id=scan_id,
            scan_type="SAST",
            target=target,
            started_at=started_at,
            completed_at=datetime.now(),
            status="completed",
            findings=findings,
            summary=self._create_summary(findings),
            metadata={
                "rules_count": len(self.compiled_rules),
                "files_scanned": kwargs.get("files_scanned", 0)
            }
        )
    
    async def _scan_directory(self, directory: Path) -> List[ScanFinding]:
        """扫描目录"""
        findings = []
        
        # Python文件
        for py_file in directory.rglob("*.py"):
            if self._should_skip(py_file):
                continue
            findings.extend(await self._scan_file(py_file, "python"))
        
        # JavaScript/TypeScript文件
        for ext in ["*.js", "*.ts", "*.jsx", "*.tsx"]:
            for js_file in directory.rglob(ext):
                if self._should_skip(js_file):
                    continue
                findings.extend(await self._scan_file(js_file, "js"))
        
        return findings
    
    def _should_skip(self, file_path: Path) -> bool:
        """是否应跳过文件"""
        skip_dirs = ["node_modules", "__pycache__", ".git", "venv", ".venv", "dist", "build"]
        return any(d in file_path.parts for d in skip_dirs)
    
    async def _scan_file(
        self,
        file_path: Path,
        lang: Optional[str] = None
    ) -> List[ScanFinding]:
        """扫描单个文件"""
        findings = []
        
        # 自动检测语言
        if lang is None:
            suffix = file_path.suffix.lower()
            if suffix == ".py":
                lang = "python"
            elif suffix in [".js", ".ts", ".jsx", ".tsx"]:
                lang = "js"
            else:
                return findings
        
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\n')
            
            for rule_name, rule in self.compiled_rules.items():
                if not rule_name.startswith(f"{lang}:"):
                    continue
                
                for pattern in rule["patterns"]:
                    for line_num, line in enumerate(lines, 1):
                        if pattern.search(line):
                            finding = ScanFinding(
                                id=f"{self._generate_scan_id()}_{line_num}",
                                title=f"{rule_name.split(':')[1].replace('_', ' ').title()} 发现",
                                description=f"在 {file_path.name} 第 {line_num} 行发现潜在安全问题",
                                severity=rule["severity"],
                                vulnerability_type=rule["vuln_type"],
                                file_path=str(file_path),
                                line_number=line_num,
                                code_snippet=line.strip()[:200],
                                cwe_id=rule["cwe"],
                                recommendation=rule["recommendation"]
                            )
                            findings.append(finding)
        except Exception as e:
            logger.error(f"扫描文件失败 {file_path}: {e}")
        
        return findings


# ==================== 依赖扫描器 ====================

@dataclass
class DependencyVulnerability:
    """依赖漏洞"""
    package: str
    version: str
    vulnerable_versions: str
    cve_id: str
    severity: SeverityLevel
    description: str
    fixed_version: Optional[str] = None
    references: List[str] = field(default_factory=list)


class DependencyScanner(SecurityScanner):
    """依赖扫描器"""
    
    # 已知漏洞数据库(示例)
    KNOWN_VULNERABILITIES = {
        "requests": [
            {
                "vulnerable_versions": "<2.25.0",
                "cve_id": "CVE-2023-32681",
                "severity": SeverityLevel.MEDIUM,
                "description": "Requests库在某些情况下可能泄露敏感信息",
                "fixed_version": "2.25.0"
            }
        ],
        "urllib3": [
            {
                "vulnerable_versions": "<1.26.5",
                "cve_id": "CVE-2021-33503",
                "severity": SeverityLevel.HIGH,
                "description": "urllib3可能导致ReDoS攻击",
                "fixed_version": "1.26.5"
            }
        ],
        "pillow": [
            {
                "vulnerable_versions": "<9.0.0",
                "cve_id": "CVE-2022-22817",
                "severity": SeverityLevel.CRITICAL,
                "description": "Pillow存在任意代码执行漏洞",
                "fixed_version": "9.0.0"
            }
        ],
        "pyyaml": [
            {
                "vulnerable_versions": "<5.4",
                "cve_id": "CVE-2020-14343",
                "severity": SeverityLevel.CRITICAL,
                "description": "PyYAML存在任意代码执行漏洞",
                "fixed_version": "5.4"
            }
        ],
        "cryptography": [
            {
                "vulnerable_versions": "<39.0.1",
                "cve_id": "CVE-2023-23931",
                "severity": SeverityLevel.HIGH,
                "description": "cryptography存在内存损坏漏洞",
                "fixed_version": "39.0.1"
            }
        ],
    }
    
    async def scan(self, target: str, **kwargs) -> ScanReport:
        """扫描依赖"""
        scan_id = self._generate_scan_id()
        started_at = datetime.now()
        findings = []
        
        target_path = Path(target)
        
        # 扫描requirements.txt
        req_files = list(target_path.rglob("requirements*.txt"))
        for req_file in req_files:
            findings.extend(await self._scan_requirements(req_file))
        
        # 扫描package.json
        pkg_files = list(target_path.rglob("package.json"))
        for pkg_file in pkg_files:
            findings.extend(await self._scan_package_json(pkg_file))
        
        # 扫描Pipfile
        pipfiles = list(target_path.rglob("Pipfile"))
        for pipfile in pipfiles:
            findings.extend(await self._scan_pipfile(pipfile))
        
        return ScanReport(
            scan_id=scan_id,
            scan_type="Dependency",
            target=target,
            started_at=started_at,
            completed_at=datetime.now(),
            status="completed",
            findings=findings,
            summary=self._create_summary(findings),
            metadata={
                "requirements_files": len(req_files),
                "package_json_files": len(pkg_files),
                "pipfiles": len(pipfiles)
            }
        )
    
    async def _scan_requirements(self, req_file: Path) -> List[ScanFinding]:
        """扫描requirements.txt"""
        findings = []
        
        try:
            content = req_file.read_text(encoding='utf-8')
            
            for line in content.split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # 解析包名和版本
                match = re.match(r'^([a-zA-Z0-9_-]+)([<>=!]+)?(.+)?$', line)
                if match:
                    package = match.group(1).lower()
                    version = match.group(3) or "latest"
                    
                    vulns = self._check_package(package, version)
                    for vuln in vulns:
                        finding = ScanFinding(
                            id=f"dep_{self._generate_scan_id()}",
                            title=f"依赖漏洞: {package}",
                            description=vuln["description"],
                            severity=vuln["severity"],
                            vulnerability_type=VulnerabilityType.DEPENDENCY_VULNERABILITY,
                            file_path=str(req_file),
                            cve_id=vuln["cve_id"],
                            recommendation=f"升级到版本 {vuln.get('fixed_version', '最新版本')}"
                        )
                        findings.append(finding)
        except Exception as e:
            logger.error(f"扫描requirements失败 {req_file}: {e}")
        
        return findings
    
    async def _scan_package_json(self, pkg_file: Path) -> List[ScanFinding]:
        """扫描package.json"""
        findings = []
        
        try:
            content = json.loads(pkg_file.read_text(encoding='utf-8'))
            
            deps = {}
            deps.update(content.get("dependencies", {}))
            deps.update(content.get("devDependencies", {}))
            
            # 检查已知漏洞包(示例)
            vulnerable_npm = {
                "lodash": {"cve": "CVE-2021-23337", "severity": SeverityLevel.HIGH},
                "axios": {"cve": "CVE-2020-28168", "severity": SeverityLevel.MEDIUM},
            }
            
            for pkg, version in deps.items():
                if pkg in vulnerable_npm:
                    vuln = vulnerable_npm[pkg]
                    finding = ScanFinding(
                        id=f"npm_{self._generate_scan_id()}",
                        title=f"NPM依赖漏洞: {pkg}",
                        description=f"{pkg}@{version}存在已知安全漏洞",
                        severity=vuln["severity"],
                        vulnerability_type=VulnerabilityType.DEPENDENCY_VULNERABILITY,
                        file_path=str(pkg_file),
                        cve_id=vuln["cve"],
                        recommendation="升级到最新版本"
                    )
                    findings.append(finding)
        except Exception as e:
            logger.error(f"扫描package.json失败 {pkg_file}: {e}")
        
        return findings
    
    async def _scan_pipfile(self, pipfile: Path) -> List[ScanFinding]:
        """扫描Pipfile"""
        findings = []
        
        try:
            content = pipfile.read_text(encoding='utf-8')
            
            # 简单解析Pipfile
            in_packages = False
            for line in content.split('\n'):
                line = line.strip()
                
                if line == "[packages]" or line == "[dev-packages]":
                    in_packages = True
                    continue
                elif line.startswith("["):
                    in_packages = False
                    continue
                
                if in_packages and "=" in line:
                    parts = line.split("=")
                    package = parts[0].strip().strip('"').lower()
                    
                    vulns = self._check_package(package, "")
                    for vuln in vulns:
                        finding = ScanFinding(
                            id=f"pipfile_{self._generate_scan_id()}",
                            title=f"Pipfile依赖漏洞: {package}",
                            description=vuln["description"],
                            severity=vuln["severity"],
                            vulnerability_type=VulnerabilityType.DEPENDENCY_VULNERABILITY,
                            file_path=str(pipfile),
                            cve_id=vuln["cve_id"],
                            recommendation=f"升级到版本 {vuln.get('fixed_version', '最新版本')}"
                        )
                        findings.append(finding)
        except Exception as e:
            logger.error(f"扫描Pipfile失败 {pipfile}: {e}")
        
        return findings
    
    def _check_package(self, package: str, version: str) -> List[Dict]:
        """检查包是否有漏洞"""
        return self.KNOWN_VULNERABILITIES.get(package, [])


# ==================== 配置扫描器 ====================

class ConfigScanner(SecurityScanner):
    """配置安全扫描器"""
    
    # 配置安全规则
    CONFIG_RULES = {
        "debug_mode": {
            "patterns": [
                (r"DEBUG\s*[=:]\s*[Tt]rue", "Python/Django DEBUG模式已启用"),
                (r"\"debug\"\s*:\s*true", "JSON配置DEBUG模式已启用"),
            ],
            "severity": SeverityLevel.MEDIUM,
            "recommendation": "生产环境禁用DEBUG模式"
        },
        "exposed_secrets": {
            "patterns": [
                (r"(?i)(secret|password|api_key|token)\s*[=:]\s*['\"][^'\"]{8,}['\"]", "发现硬编码密钥"),
            ],
            "severity": SeverityLevel.HIGH,
            "recommendation": "使用环境变量或密钥管理服务"
        },
        "insecure_cors": {
            "patterns": [
                (r"CORS_ORIGIN_ALLOW_ALL\s*=\s*True", "CORS允许所有来源"),
                (r"Access-Control-Allow-Origin:\s*\*", "CORS允许所有来源"),
            ],
            "severity": SeverityLevel.MEDIUM,
            "recommendation": "限制CORS允许的来源"
        },
        "weak_ssl": {
            "patterns": [
                (r"SSLv2|SSLv3|TLSv1\.0|TLSv1\.1", "使用弱SSL/TLS版本"),
                (r"verify\s*=\s*False", "SSL证书验证已禁用"),
            ],
            "severity": SeverityLevel.HIGH,
            "recommendation": "使用TLS 1.2或更高版本，启用证书验证"
        },
        "default_credentials": {
            "patterns": [
                (r"(?i)password\s*[=:]\s*['\"]?(admin|root|123456|password)['\"]?", "使用默认密码"),
                (r"(?i)username\s*[=:]\s*['\"]?(admin|root)['\"]?", "使用默认用户名"),
            ],
            "severity": SeverityLevel.CRITICAL,
            "recommendation": "修改默认凭证"
        },
        "insecure_binding": {
            "patterns": [
                (r"host\s*[=:]\s*['\"]?0\.0\.0\.0['\"]?", "服务绑定到所有接口"),
            ],
            "severity": SeverityLevel.LOW,
            "recommendation": "生产环境考虑绑定到特定接口"
        },
    }
    
    def __init__(self):
        self.compiled_rules = {}
        self._compile_rules()
    
    def _compile_rules(self):
        for name, rule in self.CONFIG_RULES.items():
            self.compiled_rules[name] = {
                "patterns": [(re.compile(p[0]), p[1]) for p in rule["patterns"]],
                "severity": rule["severity"],
                "recommendation": rule["recommendation"]
            }
    
    async def scan(self, target: str, **kwargs) -> ScanReport:
        """扫描配置文件"""
        scan_id = self._generate_scan_id()
        started_at = datetime.now()
        findings = []
        
        target_path = Path(target)
        
        # 配置文件模式
        config_patterns = [
            "*.yml", "*.yaml", "*.json", "*.ini", "*.conf",
            "*.env", ".env*", "*.toml", "settings.py", "config.py"
        ]
        
        for pattern in config_patterns:
            for config_file in target_path.rglob(pattern):
                if self._should_skip(config_file):
                    continue
                findings.extend(await self._scan_config_file(config_file))
        
        return ScanReport(
            scan_id=scan_id,
            scan_type="Config",
            target=target,
            started_at=started_at,
            completed_at=datetime.now(),
            status="completed",
            findings=findings,
            summary=self._create_summary(findings)
        )
    
    def _should_skip(self, file_path: Path) -> bool:
        skip_dirs = ["node_modules", "__pycache__", ".git", "venv", ".venv"]
        return any(d in file_path.parts for d in skip_dirs)
    
    async def _scan_config_file(self, file_path: Path) -> List[ScanFinding]:
        """扫描单个配置文件"""
        findings = []
        
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            
            for rule_name, rule in self.compiled_rules.items():
                for pattern, desc in rule["patterns"]:
                    matches = pattern.finditer(content)
                    for match in matches:
                        # 计算行号
                        line_num = content[:match.start()].count('\n') + 1
                        
                        finding = ScanFinding(
                            id=f"cfg_{self._generate_scan_id()}",
                            title=f"配置安全问题: {rule_name}",
                            description=desc,
                            severity=rule["severity"],
                            vulnerability_type=VulnerabilityType.SECURITY_MISCONFIGURATION,
                            file_path=str(file_path),
                            line_number=line_num,
                            code_snippet=match.group()[:100],
                            recommendation=rule["recommendation"]
                        )
                        findings.append(finding)
        except Exception as e:
            logger.error(f"扫描配置文件失败 {file_path}: {e}")
        
        return findings


# ==================== 敏感信息扫描器 ====================

class SecretScanner(SecurityScanner):
    """敏感信息扫描器"""
    
    SECRET_PATTERNS = {
        "aws_access_key": {
            "pattern": r"AKIA[0-9A-Z]{16}",
            "description": "AWS Access Key ID"
        },
        "aws_secret_key": {
            "pattern": r"(?i)aws(.{0,20})?['\"][0-9a-zA-Z/+]{40}['\"]",
            "description": "AWS Secret Access Key"
        },
        "github_token": {
            "pattern": r"ghp_[0-9a-zA-Z]{36}",
            "description": "GitHub Personal Access Token"
        },
        "github_oauth": {
            "pattern": r"gho_[0-9a-zA-Z]{36}",
            "description": "GitHub OAuth Access Token"
        },
        "private_key": {
            "pattern": r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----",
            "description": "私钥文件"
        },
        "jwt_token": {
            "pattern": r"eyJ[A-Za-z0-9-_]+\.eyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_.+/]*",
            "description": "JWT Token"
        },
        "generic_api_key": {
            "pattern": r"(?i)(api[_-]?key|apikey)['\"]?\s*[:=]\s*['\"]?([a-zA-Z0-9_-]{20,})['\"]?",
            "description": "通用API Key"
        },
        "slack_webhook": {
            "pattern": r"https://hooks\.slack\.com/services/T[a-zA-Z0-9_]{8}/B[a-zA-Z0-9_]{8}/[a-zA-Z0-9_]{24}",
            "description": "Slack Webhook URL"
        },
        "stripe_key": {
            "pattern": r"sk_live_[0-9a-zA-Z]{24}",
            "description": "Stripe Secret Key"
        },
        "google_api_key": {
            "pattern": r"AIza[0-9A-Za-z_-]{35}",
            "description": "Google API Key"
        },
    }
    
    def __init__(self):
        self.compiled_patterns = {
            name: re.compile(info["pattern"])
            for name, info in self.SECRET_PATTERNS.items()
        }
    
    async def scan(self, target: str, **kwargs) -> ScanReport:
        """扫描敏感信息"""
        scan_id = self._generate_scan_id()
        started_at = datetime.now()
        findings = []
        
        target_path = Path(target)
        
        # 排除二进制和大文件
        text_extensions = [
            ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go",
            ".rb", ".php", ".yml", ".yaml", ".json", ".xml", ".md",
            ".txt", ".env", ".conf", ".ini", ".sh", ".bat", ".ps1"
        ]
        
        for ext in text_extensions:
            for file_path in target_path.rglob(f"*{ext}"):
                if self._should_skip(file_path):
                    continue
                findings.extend(await self._scan_file_secrets(file_path))
        
        return ScanReport(
            scan_id=scan_id,
            scan_type="Secret",
            target=target,
            started_at=started_at,
            completed_at=datetime.now(),
            status="completed",
            findings=findings,
            summary=self._create_summary(findings)
        )
    
    def _should_skip(self, file_path: Path) -> bool:
        skip_dirs = ["node_modules", "__pycache__", ".git", "venv", ".venv", "dist", "build"]
        return any(d in file_path.parts for d in skip_dirs)
    
    async def _scan_file_secrets(self, file_path: Path) -> List[ScanFinding]:
        """扫描文件中的敏感信息"""
        findings = []
        
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\n')
            
            for name, pattern in self.compiled_patterns.items():
                for line_num, line in enumerate(lines, 1):
                    if pattern.search(line):
                        finding = ScanFinding(
                            id=f"secret_{self._generate_scan_id()}",
                            title=f"敏感信息泄露: {self.SECRET_PATTERNS[name]['description']}",
                            description=f"在代码中发现潜在的敏感信息",
                            severity=SeverityLevel.HIGH,
                            vulnerability_type=VulnerabilityType.SENSITIVE_DATA_EXPOSURE,
                            file_path=str(file_path),
                            line_number=line_num,
                            code_snippet=self._mask_secret(line.strip()[:100]),
                            recommendation="移除硬编码的敏感信息，使用环境变量或密钥管理服务"
                        )
                        findings.append(finding)
        except Exception as e:
            logger.error(f"扫描敏感信息失败 {file_path}: {e}")
        
        return findings
    
    def _mask_secret(self, text: str) -> str:
        """遮蔽敏感信息"""
        # 保留前4位和后4位
        for pattern in self.compiled_patterns.values():
            match = pattern.search(text)
            if match:
                secret = match.group()
                if len(secret) > 8:
                    masked = secret[:4] + "*" * (len(secret) - 8) + secret[-4:]
                    text = text.replace(secret, masked)
        return text


# ==================== 综合扫描管理器 ====================

class SecurityScanManager:
    """安全扫描管理器"""
    
    def __init__(self):
        self.sast_scanner = SASTScanner()
        self.dependency_scanner = DependencyScanner()
        self.config_scanner = ConfigScanner()
        self.secret_scanner = SecretScanner()
        self.scan_history: List[ScanReport] = []
    
    async def full_scan(self, target: str) -> Dict[str, ScanReport]:
        """执行完整安全扫描"""
        results = {}
        
        # 并行执行所有扫描
        tasks = [
            ("sast", self.sast_scanner.scan(target)),
            ("dependency", self.dependency_scanner.scan(target)),
            ("config", self.config_scanner.scan(target)),
            ("secret", self.secret_scanner.scan(target)),
        ]
        
        for name, task in tasks:
            try:
                results[name] = await task
                self.scan_history.append(results[name])
            except Exception as e:
                logger.error(f"{name}扫描失败: {e}")
        
        return results
    
    async def quick_scan(self, target: str) -> ScanReport:
        """快速扫描(仅SAST和敏感信息)"""
        sast_report = await self.sast_scanner.scan(target)
        secret_report = await self.secret_scanner.scan(target)
        
        # 合并结果
        all_findings = sast_report.findings + secret_report.findings
        
        return ScanReport(
            scan_id=sast_report.scan_id,
            scan_type="QuickScan",
            target=target,
            started_at=sast_report.started_at,
            completed_at=datetime.now(),
            status="completed",
            findings=all_findings,
            summary=self._merge_summaries([sast_report.summary, secret_report.summary])
        )
    
    def _merge_summaries(self, summaries: List[Dict[str, int]]) -> Dict[str, int]:
        """合并扫描摘要"""
        merged = {"total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for s in summaries:
            for key in merged:
                merged[key] += s.get(key, 0)
        return merged
    
    def get_critical_findings(self) -> List[ScanFinding]:
        """获取所有严重和高危发现"""
        critical = []
        for report in self.scan_history:
            for finding in report.findings:
                if finding.severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]:
                    critical.append(finding)
        return critical
    
    def generate_summary_report(self) -> Dict[str, Any]:
        """生成汇总报告"""
        all_findings = []
        for report in self.scan_history:
            all_findings.extend(report.findings)
        
        return {
            "total_scans": len(self.scan_history),
            "total_findings": len(all_findings),
            "by_severity": {
                "critical": len([f for f in all_findings if f.severity == SeverityLevel.CRITICAL]),
                "high": len([f for f in all_findings if f.severity == SeverityLevel.HIGH]),
                "medium": len([f for f in all_findings if f.severity == SeverityLevel.MEDIUM]),
                "low": len([f for f in all_findings if f.severity == SeverityLevel.LOW]),
            },
            "by_type": self._count_by_type(all_findings),
            "top_vulnerable_files": self._get_top_files(all_findings),
        }
    
    def _count_by_type(self, findings: List[ScanFinding]) -> Dict[str, int]:
        """按类型统计"""
        counts = {}
        for f in findings:
            vtype = f.vulnerability_type.value
            counts[vtype] = counts.get(vtype, 0) + 1
        return counts
    
    def _get_top_files(self, findings: List[ScanFinding], limit: int = 10) -> List[Dict]:
        """获取问题最多的文件"""
        file_counts = {}
        for f in findings:
            if f.file_path:
                file_counts[f.file_path] = file_counts.get(f.file_path, 0) + 1
        
        sorted_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)
        return [{"file": f, "count": c} for f, c in sorted_files[:limit]]


# ==================== 导出 ====================

__all__ = [
    # 类型定义
    "SeverityLevel",
    "VulnerabilityType",
    "ScanFinding",
    "ScanReport",
    "DependencyVulnerability",
    # 扫描器
    "SecurityScanner",
    "SASTScanner",
    "DependencyScanner",
    "ConfigScanner",
    "SecretScanner",
    # 管理器
    "SecurityScanManager",
]
