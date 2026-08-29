from app.services.metadata import extract_notice_metadata


def test_extract_notice_metadata() -> None:
    text = (
        "报名对象：全日制本科生。报名方式：填写报名表并发送至指定邮箱；"
        "竞赛级别：国家级A类。"
    )
    target, method, level = extract_notice_metadata(text)
    assert target == "全日制本科生"
    assert method == "填写报名表并发送至指定邮箱"
    assert level == "国家级A类"

