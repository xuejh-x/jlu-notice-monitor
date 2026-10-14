"""Extract B2 title/date/image structural controls from immutable audit HTML."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "docs/jlu-audit-evidence"
DEST = ROOT / "backend/tests/fixtures/jlu_b2"


def main():
    rows = json.loads((OLD / "results.json").read_text(encoding="utf-8"))
    specs = [("university", "https://www.jlu.edu.cn/index/tzgg.htm", "58176.htm"),
             ("student", "https://xsc.jlu.edu.cn/index/tzgg.htm", "5941.htm"),
             ("image", "https://cse.jlu.edu.cn/xytz.htm", "1381.htm"),
             ("food", "https://spxy.jlu.edu.cn/bksjy/jxxx.htm", "4120.htm")]
    DEST.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name, url, article in specs:
        r = next(r for r in rows if r["column_url"] == url)
        d = next(d for d in r["details"] if d["url"].endswith(article))
        raw_list = (OLD / r["list_snapshot"]).read_bytes()
        raw_detail = (OLD / d["snapshot"]).read_bytes()
        assert hashlib.sha256(raw_list).hexdigest() == r["list_sha256"]
        assert hashlib.sha256(raw_detail).hexdigest() == d["sha256"]
        listing = BeautifulSoup(raw_list.decode("utf-8"), "html.parser")
        anchor = next(a for a in listing.select("a[href]") if urljoin(url, a["href"]) == d["url"])
        row = anchor.find_parent(["li", "tr"]) or anchor.parent
        for text in row.find_all(string=True):
            if "王昱欢" in text:
                text.replace_with(text.replace("王昱欢", "甲同学"))
        (DEST / f"{name}.list.html").write_bytes(f'<div class="list"><ul>{row}</ul></div>'.encode("utf-8"))
        page = BeautifulSoup(raw_detail.decode("utf-8"), "html.parser")
        body = page.select_one(".v_news_content")
        # Preserve actual title/metadata hierarchy, with unrelated private prose removed.
        parent = body.find_parent("form") or body.parent.parent
        for tag in list(parent.select("script, style, noscript")):
            tag.decompose()
        if name != "image":
            body.clear()
            body.append(BeautifulSoup("<p>离线测试正文。活动时间：2026年10月14日。</p>", "html.parser"))
        (DEST / f"{name}.detail.html").write_bytes(str(parent).encode("utf-8"))
        manifest.append({"name": name, "url": url, "detail_url": d["url"], "list_sha256": r["list_sha256"],
                         "detail_sha256": d["sha256"], "captured_at": r["checked_at"],
                         "purpose": "anonymized structural control; original title/date/image preserved; not fresh HTTP"})
    (DEST / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Prepared {len(manifest)} B2 structural control pairs")


if __name__ == "__main__":
    main()
