"""Independent, scoped publication/update evidence for the B5-B audit."""
import re

from bs4 import BeautifulSoup
from app.parsers.html import CONTENT_SELECTORS, DATE_TEXT_PATTERN, in_navigation
from app.services.dates import parse_date
from app.services.normalization import normalize_whitespace

PUBLISHED = re.compile(r"(?<![\u4e00-\u9fff])(?:发布日期|发布时间|发表时间)[：:\s]*(" + DATE_TEXT_PATTERN.pattern + ")")
UPDATED = re.compile(r"(?:更新时间|更新日期|最后更新时间|最后修改时间|修改时间)[：:\s]*(" + DATE_TEXT_PATTERN.pattern + ")")


def assess_dates(html, *, list_date=None, parsed_date=None):
    soup = BeautifulSoup(html, "html.parser")
    body = next((soup.select_one(selector) for selector in CONTENT_SELECTORS if soup.select_one(selector) is not None), None)
    frame = (body.find_parent("form", attrs={"name": "_newscontent_fromname"}) or body.parent) if body is not None else None
    published, updated, unlabelled, invalid = [], [], [], []
    if soup.head:
        for node in soup.head.select("meta[content]"):
            name = str(node.get("property") or node.get("name") or "").casefold()
            if name not in {"article:published_time", "pubdate", "article:modified_time", "last-modified"}:
                continue
            value = str(node["content"])
            date = parse_date(value)
            evidence = {"kind": "head_meta", "name": name, "raw": value, "date": str(date) if date else None}
            if not date:
                invalid.append(evidence)
            else:
                (published if name in {"article:published_time", "pubdate"} else updated).append(evidence)
    if frame:
        for node in frame.select(".arc-info,.meta,.article-meta,.article-info,.news-info,.conttime,.content-bt-xia,.title3 > p.ac,time"):
            if node is body or body in node.parents or body in node.descendants or in_navigation(node):
                continue
            raw = normalize_whitespace(node.get_text(" ", strip=True))
            if len(raw) > 500:
                continue
            for pattern, group in [(PUBLISHED, published), (UPDATED, updated)]:
                for match in pattern.finditer(raw):
                    date = parse_date(match[1])
                    evidence = {"kind": "article_metadata", "raw": match[0], "date": str(date) if date else None}
                    (group if date else invalid).append(evidence)
            if node.name == "time" and node.get("itemprop") == "datePublished" and node.get("datetime"):
                date = parse_date(node["datetime"])
                evidence = {"kind": "time_datePublished", "raw": node["datetime"], "date": str(date) if date else None}
                (published if date else invalid).append(evidence)
            if not PUBLISHED.search(raw) and not UPDATED.search(raw) and parse_date(raw):
                unlabelled.append({"raw": raw, "date": str(parse_date(raw))})
    publish_dates = sorted({p["date"] for p in published})
    update_dates = sorted({p["date"] for p in updated})
    if len(publish_dates) > 1:
        verdict = "CONFLICTING_PUBLICATION_EVIDENCE"
    elif len(publish_dates) == 1 and not invalid:
        verdict = "EXPLICIT_PUBLICATION_EVIDENCE"
    elif update_dates:
        verdict = "UPDATE_TIME_ONLY_PUBLICATION_UNCONFIRMED"
    else:
        verdict = "NO_EXPLICIT_PUBLICATION_EVIDENCE"
    return {"verdict": verdict, "publication_evidence": published, "update_evidence": updated,
            "unlabelled_article_dates": unlabelled, "invalid_evidence": invalid,
            "list_date": str(list_date) if list_date else None, "parsed_date": str(parsed_date) if parsed_date else None,
            "list_matches_update": bool(list_date and str(list_date) in update_dates),
            "publication_verified": verdict == "EXPLICIT_PUBLICATION_EVIDENCE" and str(parsed_date) == publish_dates[0],
            "body_dates_used_as_publication": False}
