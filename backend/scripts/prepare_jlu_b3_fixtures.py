"""Extract the observed six-image attachment list without unrelated notice prose."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]


def main():
    evidence = ROOT / "docs/jlu-audit-evidence"
    results = json.loads((evidence / "results.json").read_text(encoding="utf-8"))
    d = next(d for r in results for d in r.get("details", []) if d["url"] == "https://csw.jlu.edu.cn/info/1095/8548.htm")
    raw = (evidence / d["snapshot"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == d["sha256"]
    soup = BeautifulSoup(raw.decode("utf-8"), "html.parser")
    listing = soup.select_one("a[href*='download.jsp']").find_parent("ul")
    for tag in list(listing.select("script")):
        tag.decompose()
    html = '<form name="_newscontent_fromname"><div class="detail-title">离线附件通知</div><div class="v_news_content">离线正文。</div>' + str(listing) + '</form>'
    dest = ROOT / "backend/tests/fixtures/jlu_b3"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "software-images.html").write_bytes(html.encode("utf-8"))
    manifest = {"url": d["url"], "captured_at": d["time"], "snapshot_sha256": d["sha256"],
                "purpose": "original attachment structure, filenames and URLs; unrelated prose removed; not fresh HTTP",
                "files": [{"filename": a.get_text(strip=True), "href": a["href"]} for a in listing.select("a[href]")]}
    assert len(manifest["files"]) == 6
    (dest / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Prepared original six-file VSB attachment fixture")


if __name__ == "__main__":
    main()
