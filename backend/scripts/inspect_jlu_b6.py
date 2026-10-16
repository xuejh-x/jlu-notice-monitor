"""Offline diagnostics for bounded P2 samples, including unknown metadata layouts."""
from collections import Counter
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
INPUT = ROOT / "docs/jlu-fix-b6/live-20261015"


def main():
    rows = json.loads((INPUT / "results.json").read_text(encoding="utf-8"))
    groups = {}
    for row in rows:
        for detail in row["details"]:
            if detail["verified"]:
                continue
            key = urlsplit(detail["url"]).hostname
            if key in groups:
                continue
            response = detail.get("response", {})
            if not response.get("html_path"):
                groups[key] = {"url": detail["url"], "reason": detail.get("reason")}
                continue
            soup = BeautifulSoup((INPUT / response["html_path"]).read_text(encoding="utf-8"), "html.parser")
            form = soup.select_one("form[name='_newscontent_fromname']") or soup.select_one(".article_details1")
            body = soup.select_one(".v_news_content,#vsb_content,.article_details1 .cont > .text")
            metadata, headings = [], []
            if form:
                for node in form.select("h1,h2,h3,h4,h5,h6,div,p,span,i"):
                    if node is body or body in node.parents or (body and body in node.descendants):
                        continue
                    label = " ".join(node.get_text(" ", strip=True).split())
                    if not label or len(label) > 280:
                        continue
                    if re.search(r"发布日期|发布时间|发表时间|作者|时间[：:]", label):
                        metadata.append({"tag": node.name, "class": node.get("class", []), "text": label})
                    if node.name.startswith("h") or re.search("title|tit|bt", " ".join(node.get("class", []))):
                        headings.append({"tag": node.name, "class": node.get("class", []), "text": label})
            groups[key] = {"url": detail["url"], "snapshot": response["html_path"], "reason": detail.get("reason"),
                           "comparison_issues": detail.get("comparison", {}).get("issues"), "headings": headings[:8], "metadata": metadata[:12],
                           "missing_attachments": detail.get("comparison", {}).get("missing_attachment_urls", [])}
    result = {"entries_so_far": len(rows), "verdicts": dict(Counter(r["verdict"] for r in rows)), "host_examples": groups}
    (INPUT.parent / "intermediate-diagnostics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
