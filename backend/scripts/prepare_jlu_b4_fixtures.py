"""Extract anonymized employment controls from this batch's saved public HTML."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]


def main():
    evidence = ROOT / "docs/jlu-fix-b4/employment-discovery-20261014"
    rows = json.loads((evidence / "inspection.json").read_text(encoding="utf-8"))
    dest = ROOT / "backend/tests/fixtures/jlu_b4"
    dest.mkdir(parents=True, exist_ok=True)
    manifest = []
    for index, row in enumerate(rows):
        name = "notices" if index == 0 else "publicity"
        raw = (evidence / row["html_path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == row["sha256"]
        soup = BeautifulSoup(raw.decode("utf-8"), "html.parser")
        lis = []
        for d in row["details"]:
            anchor = next(a for a in soup.select(".m-list-line_content h3 a[href]") if urljoin(row["url"], a["href"]) == d["url"])
            li = anchor.find_parent("li")
            for summary in li.select("p"):
                summary.string = "离线摘要，活动时间：2027-01-01。"
            for span in li.select(".m-list-line_content > span"):
                if span.get_text(strip=True).startswith("发布："):
                    span.string = "发布：离线作者"
            lis.append(str(li))
        (dest / f"{name}.list.html").write_bytes(('<ul class="m-list-line">' + ''.join(lis) + '</ul>').encode("utf-8"))
        details = []
        for count, d in enumerate(row["details"]):
            raw = (evidence / d["html_path"]).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == d["sha256"]
            page = BeautifulSoup(raw.decode("utf-8"), "html.parser")
            container = page.select_one(".m-content-container")
            body = container.select_one(".m-detail-content__container")
            body.clear()
            body.append("离线正文，公示时间2027-01-01，与创建时间无关。")
            metadata = container.select_one(".m-detail-container__info")
            for child in metadata.select("span"):
                if child.get_text(strip=True).startswith("发布："):
                    child.string = "发布：离线作者"
            for tag in list(container.select("script,style,noscript")):
                tag.decompose()
            filename = f"{name}.{count}.detail.html"
            (dest / filename).write_bytes(str(container).encode("utf-8"))
            details.append({"url": d["url"], "file": filename, "captured_at": d["time"], "sha256": d["sha256"]})
        manifest.append({"name": name, "url": row["url"], "list_sha256": row["sha256"], "captured_at": row["time"],
                         "details": details, "purpose": "anonymized structural controls; original IDs/title/date/attachment structure retained"})
    (dest / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    live = ROOT / "docs/jlu-fix-b4/live-20261014"
    if (live / "results.json").exists():
        results = json.loads((live / "results.json").read_text(encoding="utf-8"))
        controls = []
        for ident in ["kjc", "hssra", "youth", "yzb-notices"]:
            result = next(r for r in results if r["id"] == ident)
            d = result["details"][0]
            raw = (live / d["snapshot"]).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == d["sha256"]
            soup = BeautifulSoup(raw.decode("utf-8"), "html.parser")
            node = soup.select_one(".v_news_content")
            frame = node.find_parent("form", attrs={"name": "_newscontent_fromname"})
            node.clear()
            node.string = "离线正文。"
            for tag in list(frame.select("script,style,noscript")):
                tag.decompose()
            filename = ident + ".detail.html"
            (dest / filename).write_bytes(str(frame).encode("utf-8"))
            controls.append({"id": ident, "url": d["url"], "file": filename, "title": d["title"], "date": d["date"],
                             "date_semantics": "updated_only" if ident == "yzb-notices" else "publication", "sha256": d["sha256"], "captured_at": d["captured_at"]})
        denied = next(r for r in results if r["id"] == "jwc-teaching-publicity")
        raw = (live / denied["list_snapshot"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == denied["list_sha256"]
        (dest / "permission-required.html").write_bytes(raw)
        (dest / "vsb-manifest.json").write_text(json.dumps(controls, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Prepared two employment lists and six structural detail controls")


if __name__ == "__main__":
    main()
