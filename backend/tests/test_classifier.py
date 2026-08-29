from datetime import date

from app.classifier import classify_notice, score_importance


def test_algorithm_classification_and_high_score() -> None:
    title = "ICPC 校内选拔报名通知"
    content = "面向本科生，报名截止时间为2026年9月1日。"
    category = classify_notice(title, content)
    score = score_importance(title, content, category, date(2026, 9, 1), date(2026, 8, 29))
    assert category == "algorithm_competition"
    assert score >= 90


def test_low_relevance_notice() -> None:
    title = "教师招聘公告"
    category = classify_notice(title, "人事岗位信息")
    assert score_importance(title, "人事岗位信息", category) < 40

