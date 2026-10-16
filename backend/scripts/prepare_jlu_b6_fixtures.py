"""Derive small public template controls from saved B6 HTML; no HTTP."""
import hashlib
import json
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "docs/jlu-fix-b6/discovery-20261015"
OUT = ROOT / "backend/tests/fixtures/jlu_b6"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    controls = []
    rows = json.loads((INPUT / "results.json").read_text(encoding="utf-8"))
    for row in rows:
        response = row.get("response") or {}
        if not response.get("html_path"):
            continue
        raw = (INPUT / response["html_path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == response["sha256"]
        soup = BeautifulSoup(raw.decode("utf-8"), "html.parser")
        pager = soup.select_one(".pb_sys_common .p_next_d")
        if row["old_status"] == "失败" and pager and not row["inspection"].get("articles"):
            node = pager.find_parent(class_="pb_sys_common").parent
            if not node.select("ul"):
                node = node.parent
            filename = row["id"] + ".empty.html"
            content = str(node)
            kind = "vsb-empty"
        elif "www.zrlyyy.com/wujiaquery_g7yU_59.html" in row["url"]:
            filename, kind, content = "hospital.list.html", "hospital-list", str(soup.select_one("#datalist"))
        elif "www.zrlyyy.com/wujia_detail_g7yU_62/177728.html" in row["url"]:
            filename, kind, content = "hospital.detail.html", "hospital-detail", str(soup.select_one(".article_details1"))
        elif "www.zrlyyy.com/wujiaquery_g7yU_864.html" in row["url"]:
            filename, kind, content = "hospital.empty.html", "hospital-empty", str(soup.select_one("#datalist"))
        else:
            continue
        (OUT / filename).write_text(content, encoding="utf-8")
        controls.append({"kind": kind, "file": filename, "url": row["url"], "captured_at": response["time"],
                         "source_sha256": response["sha256"], "source_snapshot": str((INPUT / response["html_path"]).relative_to(ROOT)),
                         "fixture_sha256": hashlib.sha256(content.encode()).hexdigest()})
    (OUT / "manifest.json").write_text(json.dumps(controls, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"fixtures": len(controls), "empty_vsb": sum(c["kind"] == "vsb-empty" for c in controls)}))


if __name__ == "__main__":
    main()
