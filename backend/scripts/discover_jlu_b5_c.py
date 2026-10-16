"""Observe pagination markup on seventeen planned columns; never guess URLs."""
import argparse
import asyncio
import hashlib
import os
import re
from urllib.parse import urljoin

import audit_jlu_sites as audit
from bs4 import BeautifulSoup


def targets():
    values = []
    for config in audit.load_yaml("sources.yaml")["sources"]:
        for index, section in enumerate(config.get("sections", [])):
            copied = {**config, "enabled": False, "sections": [section]}
            values.append({"id": f"existing-{config['code']}-{index}", "url": section["url"],
                           "column": section.get("name", ""), "kind": "existing", "config": copied})
    ids = {r["id"] for r in audit.load_json(audit.ROOT / "docs/jlu-fix-b4/review-final-20261014/results.json", [])
           if r["verdict"] == "CONTENT_SAMPLE_PASSED"}
    for candidate in audit.load_json(audit.ROOT / "docs/jlu-fix-b4/source-candidates.json", []):
        if candidate["id"] in ids:
            values.append({**candidate, "url": candidate["config"]["base_url"], "kind": "disabled_candidate"})
    assert len(values) == 17 and len({v["url"] for v in values}) == 17
    return values


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    out = (audit.ROOT / args.output_dir).resolve()
    root = (audit.ROOT / "docs/jlu-fix-b5-c").resolve()
    assert out.is_relative_to(root) and out != root
    audit.EVIDENCE = out
    os.environ["JLU_APP_DATA_DIR"] = str(out / "runtime")
    files = ["backend/scripts/discover_jlu_b5_c.py", "backend/scripts/audit_jlu_sites.py", "backend/config/sources.yaml",
             "backend/app/sources/generic.py", "backend/app/sources/base.py", "backend/app/services/list_pagination.py",
             "docs/jlu-fix-b4/source-candidates.json", "docs/jlu-fix-b4/review-final-20261014/results.json"]
    hashes = {name: hashlib.sha256((audit.ROOT / name).read_bytes()).hexdigest() for name in files}
    previous = audit.load_json(out / "code-manifest.json", {})
    if previous and previous["files"] != hashes:
        raise RuntimeError("Changed input/code fingerprint; choose a new directory")
    audit.save_json(out / "code-manifest.json", {"time": previous.get("time", audit.now()), "files": hashes,
                    "scope": "one first-screen GET/column only, shared serial robots/rate guard; no detail/download/pagination requests"})
    from app.database.session import engine
    from sqlalchemy import event
    assert str(engine.url) == "sqlite://"
    def reject(*args):
        raise RuntimeError("B5_C_DISCOVERY_DATABASE_CONNECTION_FORBIDDEN")
    event.listen(engine, "connect", reject)
    planned = targets()
    audit.save_json(out / "targets.json", planned)
    old = {r["id"]: r for r in audit.load_json(out / "results.json", [])}
    results = []
    fetch = audit.AuditFetch()
    try:
        for target in planned:
            row = old.get(target["id"])
            if row is None:
                response = await fetch.get(target["url"])
                row = {"id": target["id"], "url": target["url"], "response": {k: v for k, v in response.items() if k != "html"},
                       "next_links": [], "pager_markup": [], "page_scripts": []}
                if response.get("ok") and not response.get("auth"):
                    soup = BeautifulSoup(response["html"], "html.parser")
                    row["next_links"] = audit.page_next(response["html"], response["final_url"])
                    seen = set()
                    for node in soup.select("a,button,span,div,script"):
                        label = node.get_text(" ", strip=True)
                        if (len(label) < 150 and re.search(r"下一页|下页|^Next$", label, re.I)) or any(re.search(r"(?:^|[_-])(?:p_pages|pagination|pager|pagebar)(?:$|[_-])", str(c), re.I) for c in node.get("class", [])):
                            markup = str(node.parent if node.name in {"a", "button", "span"} else node)[:8000]
                            if markup not in seen:
                                seen.add(markup)
                                row["pager_markup"].append(markup)
                                if len(row["pager_markup"]) == 12:
                                    break
                    row["page_scripts"] = [{"src": urljoin(response["final_url"], n["src"])} if n.get("src") else {"inline": n.get_text()[:10000]}
                                           for n in soup.select("script") if "page" in str(n).casefold() or "article/list" in str(n) or "pagination" in str(n)]
            results.append(row)
            audit.save_json(out / "results.json", results)
            print(target["id"], row["response"].get("ok"), row["next_links"], flush=True)
        audit.save_json(out / "summary.json", {"time": audit.now(), "columns": len(results), "reachable": sum(r["response"].get("ok", False) for r in results),
                        "http_attempts": fetch.request_count, "database": "sqlite://", "database_connections": 0, "formal_sources_changed": 0})
    finally:
        await fetch.close()


if __name__ == "__main__":
    asyncio.run(main())
