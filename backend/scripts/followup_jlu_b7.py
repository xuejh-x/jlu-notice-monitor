"""Capture only missing B7 HTML samples proved by immutable page links."""
import argparse
import asyncio
import hashlib
import os
import re
import shutil
from urllib.parse import urljoin, urlsplit

import audit_jlu_sites as audit
from bs4 import BeautifulSoup
from app.sources.base import SourceError

ROOT = audit.ROOT / "docs/jlu-fix-b7"


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--review", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--unit-pages", action="store_true")
    args = parser.parse_args()
    inputs, review, out = [(audit.ROOT / n).resolve() for n in [args.input, args.review, args.output]]
    assert all(p.is_relative_to(ROOT) and p != ROOT for p in [inputs, review, out]) and inputs != out
    assert (review / "summary.json").exists()
    rows = audit.load_json(review / "results.json", [])
    cache = audit.load_json(inputs / "requests.json", {})
    missing = set()
    allowed = set()
    for row in rows:
        for message in [row.get("reason", ""), *[d.get("reason", "") for d in row["details"]]]:
            missing.update(re.findall(r"OFFLINE_URL_NOT_CAPTURED: (https?://\S+)", message or ""))
        pages = [row.get("response", {}), *[p["response"] for p in row["pages"]]]
        for page in pages:
            if not page.get("html_path"):
                continue
            raw = (inputs / page["html_path"]).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == page["sha256"]
            for a in BeautifulSoup(raw.decode("utf-8"), "html.parser").select("a[href]"):
                u = urljoin(page["final_url"], a["href"].strip())
                if urlsplit(u).hostname == urlsplit(row["url"]).hostname and not re.search(r"\.(?:pdf|docx?|xlsx?|zip|rar|png|jpe?g)(?:[?#]|$)|download\.jsp", u, re.I):
                    allowed.add(u)
    units = ["https://pro.jlu.edu.cn/xzfwzx.htm", "https://press.jlu.edu.cn/gywm/cbsjj.htm"] if args.unit_pages else []
    if units:
        for r in cache.values():
            if not r.get("ok") or not r.get("html_path") or urlsplit(r["url"]).hostname not in {"pro.jlu.edu.cn", "press.jlu.edu.cn"}:
                continue
            raw = (inputs / r["html_path"]).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == r["sha256"]
            allowed.update(urljoin(r["final_url"], a["href"].strip()) for a in BeautifulSoup(raw.decode("utf-8"), "html.parser").select("a[href]"))
    urls = sorted((missing | set(units)) - cache.keys())
    assert 0 < len(urls) <= 32 and all(u in allowed and urlsplit(u).hostname != "oa.jlu.edu.cn" for u in urls), urls
    audit.EVIDENCE = out
    os.environ["JLU_APP_DATA_DIR"] = str(out / "runtime")
    names = ["backend/scripts/followup_jlu_b7.py", "backend/scripts/audit_jlu_sites.py", "backend/app/parsers/html.py",
             "backend/app/services/deduplication.py", "backend/app/sources/generic.py", "backend/app/services/source_security.py", "backend/app/services/tls.py", "backend/config/sources.yaml"]
    hashes = {n: hashlib.sha256((audit.ROOT / n).read_bytes()).hexdigest() for n in names}
    hashes.update({"input/" + n: hashlib.sha256((inputs / n).read_bytes()).hexdigest() for n in ["requests.json", "validation-targets.json", "code-manifest.json"]})
    hashes["review/results.json"] = hashlib.sha256((review / "results.json").read_bytes()).hexdigest()
    old = audit.load_json(out / "code-manifest.json", {})
    assert not old or old["files"] == hashes
    audit.save_json(out / "code-manifest.json", {"time": old.get("time", audit.now()), "files": hashes, "urls": urls,
        "input_dir": str(inputs.relative_to(audit.ROOT)), "review_dir": str(review.relative_to(audit.ROOT)),
        "limits": "<=32 literal-link HTML URLs; serial existing robots/rate limits; no known failure retries/OA/downloads"})
    from app.database.session import engine
    from sqlalchemy import event
    assert str(engine.url) == "sqlite://"
    def reject(*_):
        raise RuntimeError("B7_FOLLOWUP_DATABASE_FORBIDDEN")
    event.listen(engine, "connect", reject)
    fetch = audit.AuditFetch()
    if not fetch.cache:
        for key, value in cache.items():
            if value.get("html_path"):
                source = inputs / value["html_path"]
                assert hashlib.sha256(source.read_bytes()).hexdigest() == value["sha256"]
                dest = out / value["html_path"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
            fetch.cache[key] = value
        audit.save_json(out / "requests.json", fetch.cache)
    shutil.copy2(inputs / "validation-targets.json", out / "validation-targets.json")
    results = []
    try:
        for url in urls:
            r = await fetch.get(url)
            results.append({k: v for k, v in r.items() if k != "html"})
            audit.save_json(out / "results.json", results)
            print(url, r.get("ok"), flush=True)
        audit.save_json(out / "summary.json", {"time": audit.now(), "new_html_urls": len(urls), "successful": sum(r.get("ok", False) for r in results),
            "http_attempts_process": fetch.request_count, "application_db_connections": 0, "downloads": 0, "oa_requests": 0})
    finally:
        await fetch.close()


if __name__ == "__main__":
    asyncio.run(main())
