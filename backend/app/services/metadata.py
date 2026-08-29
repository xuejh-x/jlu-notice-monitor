from __future__ import annotations

import re


def _labeled_value(text: str, labels: tuple[str, ...]) -> str | None:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"(?:{label_pattern})\s*[：:]\s*(.{{2,200}}?)(?=[。；;]|(?:\s+[一二三四五六七八九十]+、)|$)",
        text,
        re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def extract_notice_metadata(text: str) -> tuple[str | None, str | None, str | None]:
    target_students = _labeled_value(
        text, ("报名对象", "参赛对象", "申请对象", "申报对象", "面向对象")
    )
    registration_method = _labeled_value(
        text, ("报名方式", "申请方式", "申报方式", "提交方式")
    )
    level_match = re.search(
        r"(?:竞赛级别|比赛级别|赛事级别)\s*[：:]\s*([^。；;]{2,50})",
        text,
        re.IGNORECASE,
    )
    competition_level = level_match.group(1).strip() if level_match else None
    if competition_level is None:
        simple_level = re.search(r"(?<![\w])(?:国家级|省级|校级|国际级|A类|B类|C类)(?![\w])", text)
        competition_level = simple_level.group(0) if simple_level else None
    return target_students, registration_method, competition_level

