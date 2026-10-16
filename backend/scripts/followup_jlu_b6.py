"""Fetch only saved-list samples missing after category/whitespace corrections."""
import asyncio
import argparse
import hashlib
import os
import shutil
from urllib.parse import urljoin, urlsplit

import audit_jlu_sites as audit
from bs4 import BeautifulSoup
from app.sources.base import SourceError


async def main():
    root = audit.ROOT / "docs/jlu-fix-b6"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", default="live-20261015")
    parser.add_argument("--review-dir", default="review-3-20261015")
    parser.add_argument("--output-dir", default="followup-20261015")
    args = parser.parse_args()
    inputs, review, out = [(root / name).resolve() for name in [args.input_dir, args.review_dir, args.output_dir]]
    assert all(p.is_relative_to(root) and p != root for p in [inputs, review, out]) and inputs != out
    assert (review / "summary.json").exists(), "Wait for full offline review"
    reviewed = audit.load_json(review / "results.json", [])
    missing = sorted({d["url"] for r in reviewed for d in r["details"] if str(d.get("reason", "")).startswith("OFFLINE_URL_NOT_CAPTURED:")})
    # Every follow-up must be a literal link in a saved, hash-checked list page
    # and must stay on the corresponding original column's host.
    allowed = set()
    for row in reviewed:
        for page in row["pages"]:
            record = page["response"]
            raw = (inputs / record["html_path"]).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == record["sha256"]
            for anchor in BeautifulSoup(raw.decode("utf-8"), "html.parser").select("a[href]"):
                target = urljoin(record["final_url"], anchor["href"].strip())
                if urlsplit(target).hostname == urlsplit(row["url"]).hostname and urlsplit(target).hostname != "oa.jlu.edu.cn":
                    allowed.add(target)
    assert 0 < len(missing) <= 8 and all(u in allowed for u in missing)
    names = ["backend/scripts/followup_jlu_b6.py", "backend/scripts/audit_jlu_sites.py", "backend/app/sources/generic.py",
             "backend/app/services/source_security.py", "backend/app/services/tls.py", "backend/config/sources.yaml"]
    hashes = {n: hashlib.sha256((audit.ROOT / n).read_bytes()).hexdigest() for n in names}
    hashes.update({"input/" + n: hashlib.sha256((inputs / n).read_bytes()).hexdigest() for n in ["requests.json", "code-manifest.json"]})
    hashes["review/results.json"] = hashlib.sha256((review / "results.json").read_bytes()).hexdigest()
    audit.EVIDENCE = out
    os.environ["JLU_APP_DATA_DIR"] = str(out / "runtime")
    prior = audit.load_json(out / "code-manifest.json", {})
    assert not prior or (prior["files"] == hashes and prior["urls"] == missing), "Changed code/input; preserve previous run"
    audit.save_json(out / "code-manifest.json", {"time": prior.get("time", audit.now()), "files": hashes, "urls": missing,
        "scope": "Only corrected samples proved by exact saved list anchors; no known failure retry, attachments, OA or Cloud traffic", "limits": "<=8 unique detail URLs; serial audit robots/rates; max2 transient attempts",
        "input_dir": str(inputs.relative_to(audit.ROOT)), "review_dir": str(review.relative_to(audit.ROOT))})
    from app.database.session import engine
    from sqlalchemy import event
    assert str(engine.url) == "sqlite://"
    def reject(*args):
        raise RuntimeError("B6_FOLLOWUP_DATABASE_FORBIDDEN")
    event.listen(engine, "connect", reject)
    fetch = audit.AuditFetch()
    if not fetch.cache:
        for key, record in audit.load_json(inputs / "requests.json", {}).items():
            if record.get("html_path"):
                source = inputs / record["html_path"]
                assert hashlib.sha256(source.read_bytes()).hexdigest() == record["sha256"]
                destination = out / record["html_path"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            fetch.cache[key] = record
        audit.save_json(out / "requests.json", fetch.cache)
    results = []
    try:
        for url in missing:
            value = await fetch.get(url)
            results.append({k: v for k, v in value.items() if k != "html"})
            audit.save_json(out / "results.json", results)
            print(url, value.get("ok"), value.get("error", ""), flush=True)
        audit.save_json(out / "summary.json", {"time": audit.now(), "new_article_urls": len(missing), "successful": sum(r.get("ok", False) for r in results),
             "http_attempts_this_session": fetch.request_count, "application_db_connections": 0, "complete_downloads": 0, "oa_requests": 0})
    finally:
        await fetch.close()


if __name__ == "__main__":
    asyncio.run(main())
