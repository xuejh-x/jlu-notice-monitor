"""Compact offline diagnostics of real B7 failures; no application/database imports."""
import json
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "docs/jlu-fix-b7/live-20261015"


def main():
    rows = json.loads((INPUT / "results.json").read_text(encoding="utf-8"))
    output = []
    seen = set()
    for r in rows:
        if r["verdict"] in {"BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN", "VERIFIED_EMPTY_COLUMN"}:
            continue
        case = {"url": r["url"], "institution": r["institution"], "verdict": r["verdict"], "reason": r["reason"],
                "missing_refs": r.get("missing_reference_urls"), "unexpected": r.get("unexpected_urls"), "details": []}
        for d in r["details"]:
            issues = d.get("comparison", {}).get("issues", [])
            key = (urlsplit(d["url"]).hostname, tuple(issues), d.get("reason"))
            if d["verified"] or key in seen:
                continue
            seen.add(key)
            detail = {"url": d["url"], "issues": issues, "reason": d.get("reason"), "snapshot": d.get("response", {}).get("html_path")}
            if detail["snapshot"]:
                soup = BeautifulSoup((INPUT / detail["snapshot"]).read_text(encoding="utf-8"), "html.parser")
                body = soup.select_one(".v_news_content, #vsb_content, .article-content, .content")
                if body:
                    frame = body.find_parent("form", attrs={"name": "_newscontent_fromname"}) or body.parent.parent
                    clone = BeautifulSoup(str(frame), "html.parser")
                    for n in clone.select("script,style"):
                        n.decompose()
                    b = clone.select_one(".v_news_content, #vsb_content, .article-content, .content")
                    if b:
                        b.clear()
                        b.append("[BODY OMITTED]")
                    detail["frame"] = str(clone)[:2100]
            case["details"].append(detail)
        output.append(case)
    (ROOT / "docs/jlu-fix-b7/initial-diagnostics.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
