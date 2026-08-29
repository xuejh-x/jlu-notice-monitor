from app.services.normalization import canonicalize_url, content_hash, normalize_title


def test_normalize_title() -> None:
    assert normalize_title("【转发】关于第 41 次 CCF CSP 认证报名的通知") == "第41次ccfcsp认证报名的"


def test_canonical_url_removes_tracking_and_fragment() -> None:
    value = canonicalize_url("HTTPS://CCST.JLU.EDU.CN/info/1.htm?utm_source=x&a=1#top")
    assert value == "https://ccst.jlu.edu.cn/info/1.htm?a=1"


def test_content_hash_is_whitespace_stable_and_sensitive() -> None:
    assert content_hash("标题", "正文  内容") == content_hash("标题", "正文 内容")
    assert content_hash("标题", "正文") != content_hash("标题", "正文已更新")
