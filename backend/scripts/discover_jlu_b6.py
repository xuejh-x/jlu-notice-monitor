"""Serial, resumable P2 first-screen inspection, no crawling or production DB."""
import argparse
import asyncio
from collections import Counter
import hashlib
import os
import re
from urllib.parse import urljoin, urlsplit

import audit_jlu_sites as audit
from bs4 import BeautifulSoup
from app.parsers.html import in_navigation
from app.sources.base import SourceError


def compact(record):
    return {k: v for k, v in record.items() if k != "html"}


def inspect(html, url):
    soup = BeautifulSoup(html, "html.parser")
    info = {"page_title": soup.title.get_text(strip=True) if soup.title else "", "parser_error": None,
            "permission_text": bool(re.search("没有访问当前栏目的权限|无权访问当前栏目", soup.get_text())),
            "empty_nodes": [{"selector": s, "text": audit.text(n)[:160]} for s in [".p_t", ".empty-data", ".pb_sys_common", ".list3"]
                            for n in soup.select(s) if re.search(r"共\s*0\s*条|暂无|没有相关信息", audit.text(n))],
            "articles": [], "next_links": audit.page_next(html, url)}
    try:
        items = audit.parse_list_html(html, url)
        info["auto_items"] = [i.model_dump(mode="json") for i in items]
    except ValueError as exc:
        info["auto_items"] = []
        info["parser_error"] = str(exc)
    for a in soup.select("a[href]"):
        if in_navigation(a):
            continue
        target = urljoin(url, a["href"])
        if re.search(r"/info/[^/]+/[^/]+\.html?$|/(?:wujia_detail|tongzhi_detail)[^/]+/\d+\.html?$", urlsplit(target).path):
            parent = a.find_parent(["li", "tr"]) or a.find_parent(class_="li") or a.parent
            info["articles"].append({"url": target, "text": audit.text(a)[:150], "row": audit.text(parent)[:250],
                                     "parent_tag": parent.name, "parent_class": parent.get("class", [])})
    for selector in ["#datalist", ".article_details1", ".list", ".news_list", ".newslist", ".list3", ".right_list"]:
        nodes = soup.select(selector)
        if nodes:
            info.setdefault("containers", {})[selector] = [{"chars": len(audit.text(n)), "head": audit.text(n)[:160]} for n in nodes[:2]]
    return info


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    root = audit.ROOT / "docs/jlu-fix-b6"
    out = (audit.ROOT / args.output_dir).resolve()
    assert out.is_relative_to(root) and out != root
    audit.EVIDENCE = out
    os.environ["JLU_APP_DATA_DIR"] = str(out / "runtime")
    files = ["backend/scripts/discover_jlu_b6.py", "backend/scripts/audit_jlu_sites.py", "backend/app/parsers/html.py",
             "backend/app/sources/generic.py", "backend/app/services/source_security.py", "backend/app/services/tls.py",
             "backend/config/sources.yaml", "docs/jlu-fix-b6/targets.json"]
    hashes = {p: hashlib.sha256((audit.ROOT / p).read_bytes()).hexdigest() for p in files}
    old = audit.load_json(out / "code-manifest.json", {})
    assert not old or old["files"] == hashes, "Changed code/input; use a new output directory"
    audit.save_json(out / "code-manifest.json", {"time": old.get("time", audit.now()), "files": hashes,
        "scope": "164 P2 entries, one screen each; original failures also inspect exact official homepage",
        "limits": "serial, global >=1s/origin >=1.2s, robots, 12s timeout, at most 2 transient attempts",
        "database": "sqlite://", "oa_deferred": True, "downloads": 0})
    from app.database.session import engine
    from sqlalchemy import event
    assert str(engine.url) == "sqlite://"
    db_attempts = []
    def reject(*args):
        db_attempts.append(audit.now())
        raise RuntimeError("B6_APPLICATION_DATABASE_CONNECTION_FORBIDDEN")
    event.listen(engine, "connect", reject)
    fetch = audit.AuditFetch()
    results = []
    previous = {r["id"]: r for r in audit.load_json(out / "results.json", [])}
    targets = audit.load_json(root / "targets.json", [])
    try:
        for target in sorted(targets, key=lambda t: t["old_status"] != "失败"):
            row = previous.get(target["id"])
            if row is None:
                row = {**target, "checked_at": audit.now(), "formal_admission": False}
                if urlsplit(target["url"]).hostname == "oa.jlu.edu.cn":
                    row.update(verdict="DEFERRED_OA_BY_USER", reason="Login reference; OA network/status work deferred", response=None)
                else:
                    response = await fetch.get(target["url"])
                    row["response"] = compact(response)
                    row["inspection"] = inspect(response["html"], response["final_url"]) if response.get("ok") else {}
                    row["verdict"] = "FIRST_SCREEN_CAPTURED" if response.get("ok") else "ACCESS_BLOCKED"
                    if target["old_status"] == "失败" and target["site_url"]:
                        home = await fetch.get(target["site_url"])
                        row["home_response"] = compact(home)
                        if home.get("ok"):
                            row["home_column_links"] = audit.column_links(home["html"], home["final_url"])
            results.append(row)
            audit.save_json(out / "results.json", results)
            inspection = row.get("inspection", {})
            print(len(results), target["institution"], target["column"], row["verdict"],
                  "auto=" + str(len(inspection.get("auto_items", []))), "refs=" + str(len(inspection.get("articles", []))),
                  "permission=" + str(inspection.get("permission_text", False)), "empty=" + str(bool(inspection.get("empty_nodes"))), flush=True)
        assert not db_attempts
        audit.save_json(out / "summary.json", {"time": audit.now(), "entries": len(results), "verdicts": dict(Counter(r["verdict"] for r in results)),
            "http_attempts_this_session": fetch.request_count, "requests_cached": len(fetch.cache), "application_db_connections": 0,
            "cloud_production_verified": False, "complete_downloads": 0, "oa_requests": 0})
    finally:
        await fetch.close()


if __name__ == "__main__":
    asyncio.run(main())
