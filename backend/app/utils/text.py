# 地方志数据智能管理系统 - 文本处理工具
"""文本清洗、关键词提取、格式化等工具"""

import re
import html
from typing import List, Optional, Tuple
from datetime import datetime
import jieba
import jieba.analyse


def clean_text(text: str) -> str:
    """
    清洗文本：去除多余空白、特殊字符
    
    Args:
        text: 原始文本
        
    Returns:
        清洗后的文本
    """
    if not text:
        return ""
    
    # 去除HTML标签
    text = remove_html_tags(text)
    
    # 统一空白字符
    text = normalize_whitespace(text)
    
    # 去除控制字符
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    
    return text.strip()


def remove_html_tags(text: str) -> str:
    """
    移除HTML标签
    
    Args:
        text: 含HTML标签的文本
        
    Returns:
        纯文本
    """
    if not text:
        return ""
    
    # 解码HTML实体
    text = html.unescape(text)
    
    # 移除标签
    text = re.sub(r'<[^>]+>', '', text)
    
    return text


def normalize_whitespace(text: str) -> str:
    """
    规范化空白字符
    
    Args:
        text: 原始文本
        
    Returns:
        规范化后的文本
    """
    if not text:
        return ""
    
    # 将多个空白字符替换为单个空格
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def truncate_text(text: str, max_length: int = 200, suffix: str = "...") -> str:
    """
    截断文本
    
    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 截断后缀
        
    Returns:
        截断后的文本
    """
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def highlight_matches(
    text: str,
    keywords: List[str],
    tag: str = "mark",
    css_class: Optional[str] = None
) -> str:
    """
    高亮匹配的关键词
    
    Args:
        text: 原始文本
        keywords: 要高亮的关键词列表
        tag: HTML标签
        css_class: CSS类名
        
    Returns:
        带高亮标记的文本
    """
    if not text or not keywords:
        return text
    
    class_attr = f' class="{css_class}"' if css_class else ""
    
    for keyword in keywords:
        if keyword:
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            text = pattern.sub(f'<{tag}{class_attr}>\\g<0></{tag}>', text)
    
    return text


def extract_keywords(
    text: str,
    top_k: int = 10,
    method: str = "tfidf"
) -> List[str]:
    """
    提取关键词
    
    Args:
        text: 文本内容
        top_k: 返回关键词数量
        method: 提取方法 (tfidf/textrank)
        
    Returns:
        关键词列表
    """
    if not text:
        return []
    
    if method == "textrank":
        keywords = jieba.analyse.textrank(text, topK=top_k)
    else:
        keywords = jieba.analyse.extract_tags(text, topK=top_k)
    
    return keywords


def extract_numbers(text: str) -> List[str]:
    """
    提取文本中的数字
    
    Args:
        text: 原始文本
        
    Returns:
        数字列表
    """
    if not text:
        return []
    
    # 匹配整数、小数、百分比等
    pattern = r'-?\d+\.?\d*%?'
    return re.findall(pattern, text)


def extract_dates(text: str) -> List[str]:
    """
    提取文本中的日期
    
    Args:
        text: 原始文本
        
    Returns:
        日期字符串列表
    """
    if not text:
        return []
    
    patterns = [
        r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?',  # 2024-01-01 or 2024年1月1日
        r'\d{4}[-/年]\d{1,2}[月]?',                # 2024-01 or 2024年1月
        r'\d{4}年',                                 # 2024年
    ]
    
    dates = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        dates.extend(matches)
    
    return list(set(dates))


def segment_text(text: str, use_paddle: bool = False) -> List[str]:
    """
    中文分词
    
    Args:
        text: 文本内容
        use_paddle: 是否使用paddle模式
        
    Returns:
        分词结果列表
    """
    if not text:
        return []
    
    if use_paddle:
        jieba.enable_paddle()
    
    return list(jieba.cut(text))


def calculate_similarity(text1: str, text2: str) -> float:
    """
    计算两段文本的相似度（基于Jaccard系数）
    
    Args:
        text1: 文本1
        text2: 文本2
        
    Returns:
        相似度 (0-1)
    """
    if not text1 or not text2:
        return 0.0
    
    words1 = set(jieba.cut(text1))
    words2 = set(jieba.cut(text2))
    
    intersection = words1 & words2
    union = words1 | words2
    
    if not union:
        return 0.0
    
    return len(intersection) / len(union)


def count_words(text: str) -> int:
    """
    统计词数
    
    Args:
        text: 文本内容
        
    Returns:
        词数
    """
    if not text:
        return 0
    
    words = jieba.cut(text)
    return sum(1 for _ in words)


def count_characters(text: str, include_spaces: bool = False) -> int:
    """
    统计字符数
    
    Args:
        text: 文本内容
        include_spaces: 是否包含空格
        
    Returns:
        字符数
    """
    if not text:
        return 0
    
    if include_spaces:
        return len(text)
    else:
        return len(text.replace(" ", "").replace("\n", "").replace("\t", ""))


def extract_sentences(text: str) -> List[str]:
    """
    提取句子
    
    Args:
        text: 文本内容
        
    Returns:
        句子列表
    """
    if not text:
        return []
    
    # 按句号、问号、感叹号分割
    sentences = re.split(r'[。！？!?.]+', text)
    return [s.strip() for s in sentences if s.strip()]


def mask_sensitive_info(text: str) -> str:
    """
    脱敏敏感信息
    
    Args:
        text: 原始文本
        
    Returns:
        脱敏后的文本
    """
    if not text:
        return ""
    
    # 身份证号
    text = re.sub(r'\d{17}[\dXx]', '***************', text)
    
    # 手机号
    text = re.sub(r'1[3-9]\d{9}', '***********', text)
    
    # 邮箱
    text = re.sub(r'[\w.-]+@[\w.-]+\.\w+', '***@***.com', text)
    
    return text
