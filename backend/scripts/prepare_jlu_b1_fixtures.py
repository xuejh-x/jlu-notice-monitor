"""Create small, anonymized structural fixtures from the saved audit evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/jlu-audit-evidence"
DEST = ROOT / "backend/tests/fixtures/jlu_b1"
CONTENT = [".v_news_content", "#vsb_content", ".article-content", ".article_content", ".news_content", ".content"]


def write(name, html):
    (DEST / name).write_bytes(html.encode("utf-8"))


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    results = json.loads((EVIDENCE / "results.json").read_text(encoding="utf-8"))
    manifest = []
    for r in results:
        if not r.get("configured_source") or r["configured_source"] == "oa":
            continue
        d = next(d for d in r["details"] if d.get("content_chars", 0) > 0)
        raw_list = (EVIDENCE / r["list_snapshot"]).read_bytes()
        raw_detail = (EVIDENCE / d["snapshot"]).read_bytes()
        soup = BeautifulSoup(raw_list, "html.parser")
        anchor = next(a for a in soup.select("a[href]") if urljoin(r["column_url"], str(a["href"])) == d["url"])
        row = anchor.find_parent(["li", "tr"]) or anchor.parent
        for a in row.select("a"):
            a.clear()
            a.append("离线样本通知")
            if a.has_attr("title"):
                a["title"] = "离线样本通知"
        # Retain source date/anchor structure, remove article prose/identities.
        for paragraph in row.select("p"):
            paragraph.string = "离线样本摘要"
        listing = f"<html><body><div class='list'><ul>{row}</ul></div></body></html>"
        page = BeautifulSoup(raw_detail, "html.parser")
        node = next(page.select_one(s) for s in CONTENT if page.select_one(s) is not None)
        for unwanted in node.select("script, style, noscript"):
            unwanted.decompose()
        for string in list(node.find_all(string=True)):
            if string.strip():
                string.replace_with("离线正文样本。")
        for a in node.select("a[href]"):
            a.string = "附件样本.xlsx" if ".xls" in str(a["href"]) else "离线正文链接"
        name = r["configured_source"] + ("_undergraduate" if "bkjxtz" in r["column_url"] else "_" + Path(r["column_url"]).stem)
        write(name + ".list.html", listing)
        write(name + ".detail.html", f"<html><body><h1>离线样本通知</h1>{node}</body></html>")
        manifest.append({"name": name, "url": r["column_url"], "detail_url": d["url"],
                         "list_sha256": hashlib.sha256(raw_list).hexdigest(), "detail_sha256": hashlib.sha256(raw_detail).hexdigest(),
                         "checked_at": r["checked_at"], "purpose": "anonymized structural positive control; not a live verification"})
    r = next(r for r in results if r["column_url"] == "https://auto.jlu.edu.cn/zsxx.htm")
    soup = BeautifulSoup((EVIDENCE / r["list_snapshot"]).read_bytes(), "html.parser")
    nav = next(ul for ul in soup.select("ul") if ul.select("a[href]") and not ul.select("a[href*='info/']"))
    write("empty-column.html", f"<html><body>{nav}<div class='list3'></div><span class='p_t'>共0条</span></body></html>")
    manifest.append({"name": "empty-column", "url": r["column_url"], "list_sha256": r["list_sha256"],
                     "purpose": "real zero-count list with navigation; remove personal information and unrelated markup"})
    (DEST / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Prepared {len(manifest)} structural controls; existing OA fixtures remain separate.")


if __name__ == "__main__":
    main()
