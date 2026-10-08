from __future__ import annotations

import re
import unicodedata
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from app.sources.base import SinglePageSource, SourceError

SECTION_LABELS = {
    "subjects": "比赛科目", "schedule": "参赛日程", "organization": "组织管理",
    "registration": "院校报名", "policy": "参赛相关政策", "support": "鼓励措施",
}
SCHOOL_HEADINGS = {"组织管理": "organization", "院校报名": "registration",
                   "权威认可": "policy", "鼓励措施": "support"}
EDITION = re.compile(r"第\s*(\d+)\s*届蓝桥杯.*?(比赛科目|参赛日程)")


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).replace("\u200b", "")
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    value = re.sub(r"\s*([:;，。])\s*", r"\1", value)
    return value.rstrip("。;，,")


def _text(node: Tag, page_url: str) -> str:
    # Exclude nested lists so their entries retain their parent context.
    clone = BeautifulSoup(str(node), "html.parser")
    for nested in clone.select("ul, ol, table, script, style"):
        nested.decompose()
    for link in clone.select("a[href]"):
        url = urljoin(page_url, str(link["href"]))
        if url.startswith(("https://", "http://")):
            link.append(f" ({url})")
    for br in clone.select("br"):
        br.replace_with(" ")
    # Inline emphasis must not introduce artificial spaces into a word.
    return normalize_text(clone.get_text("", strip=False))


def _lines(node: Tag, page_url: str, *, policy: bool = False, prefix: str = "") -> list[str]:
    if node.name in {"script", "style", "nav", "footer"}:
        return []
    if node.name == "table":
        rows = node.find_all("tr")
        selected = [row for row in rows if not policy or "蓝桥杯" in row.get_text()]
        if policy and selected and rows and rows[0] not in selected:
            selected.insert(0, rows[0])
        return [normalize_text(" | ".join(cell.get_text(" ", strip=True)
                                         for cell in row.find_all(["td", "th"]))) for row in selected]
    if node.name in {"li", "p"}:
        own = _text(node, page_url)
        line = f"{prefix}{own}" if own else ""
        result = [line] if line else []
        for nested in node.find_all(["ul", "ol", "table"], recursive=False):
            result.extend(_lines(nested, page_url, policy=policy, prefix=f"{line} / " if line else prefix))
        return result
    if node.name in {"ul", "ol", "div", "section", "blockquote"}:
        result: list[str] = []
        for index, child in enumerate(node.find_all(recursive=False), 1):
            child_prefix = f"{prefix}{index}. " if node.name == "ol" else prefix
            result.extend(_lines(child, page_url, policy=policy, prefix=child_prefix))
        return result
    text = _text(node, page_url)
    return [f"{prefix}{text}"] if text else []


class LanqiaoSource(SinglePageSource):
    def parse_snapshot(self, html: str) -> dict[str, Any]:
        if len(html) > 2_000_000:
            raise SourceError("LQB_PARSER_FAILED: page too large")
        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one(".markdown-body") or soup.body or soup
        headings = root.find_all(["h1", "h2"])
        editions: dict[int, dict[str, Tag]] = {}
        school: dict[str, Tag] = {}
        in_school = False
        for heading in headings:
            title = normalize_text(heading.get_text(" ", strip=True))
            if heading.name == "h1":
                in_school = "蓝桥杯" in title and "吉林大学" in title and "累计" not in title
            match = EDITION.search(title)
            if match:
                key = "subjects" if match[2] == "比赛科目" else "schedule"
                entries = editions.setdefault(int(match[1]), {})
                if key in entries:
                    raise SourceError("LQB_PARSER_FAILED: ambiguous edition sections")
                entries[key] = heading
            label = title.strip("〖〗【】[] ")
            if in_school and label in SCHOOL_HEADINGS:
                key = SCHOOL_HEADINGS[label]
                if key in school:
                    raise SourceError("LQB_PARSER_FAILED: ambiguous school sections")
                school[key] = heading
        if not editions:
            raise SourceError("LQB_PARSER_FAILED: current edition not recognized")
        edition = max(editions)
        selected = {**editions[edition], **school}
        if set(selected) != set(SECTION_LABELS):
            raise SourceError("LQB_PARSER_FAILED: required sections missing or edition inconsistent")
        sections: dict[str, list[str]] = {}
        for key, heading in selected.items():
            lines: list[str] = []
            for sibling in heading.next_siblings:
                if isinstance(sibling, Tag):
                    if sibling.name in {"h1", "h2", "hr"}:
                        break
                    lines.extend(_lines(sibling, self.base_url, policy=key == "policy"))
            lines = [line for line in lines if line]
            if not lines or sum(map(len, lines)) > 40_000:
                raise SourceError(f"LQB_CONTENT_INVALID: empty or excessive section {key}")
            # Subject list order is editorial; registration step order is meaningful.
            sections[key] = sorted(set(lines)) if key == "subjects" else lines
        return {"edition": edition, "sections": sections}
