"""Bounded public B2 spot checks and raw-byte encoding diagnosis; no DB writes."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re

import audit_jlu_sites as audit
from app.parsers import parse_detail_html
from app.schemas.notice import NoticeCandidate


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output = (audit.ROOT / args.output_dir).resolve()
    assert output.is_relative_to(audit.ROOT / "docs/jlu-fix-b2")
    audit.EVIDENCE = output
    os.environ["JLU_APP_DATA_DIR"] = str(output / "runtime")
    files = ["backend/app/parsers/html.py", "backend/app/sources/generic.py", "backend/app/services/tls.py",
             "backend/app/services/source_security.py", "backend/scripts/probe_jlu_b2.py"]
    fingerprint = {name: hashlib.sha256((audit.ROOT / name).read_bytes()).hexdigest() for name in files}
    manifest = output / "code-manifest.json"
    if (output / "spot-results.json").exists():
        previous = audit.load_json(manifest, {})
        if previous.get("files") != fingerprint:
            raise RuntimeError("Probe fingerprint changed or was not recorded; use a new output directory")
    audit.save_json(manifest, {"time": audit.now(), "files": fingerprint, "database": "sqlite://"})
    fetch = audit.AuditFetch()
    records = []
    controls = [("https://www.jlu.edu.cn/info/1095/58176.htm", "校级历史标题样本"),
                ("https://xsc.jlu.edu.cn/info/1048/5941.htm", "学工发布日期样本"),
                ("https://cse.jlu.edu.cn/info/1003/1381.htm", "图片正文样本")]
    try:
        for url, name in controls:
            r = await fetch.get(url)
            row = {k: v for k, v in r.items() if k != "html"}
            row["sample"] = name
            if r.get("ok") and not r.get("auth"):
                try:
                    parsed = parse_detail_html(r["html"], r["final_url"], NoticeCandidate(title=name, url=url))
                    row.update(title=parsed.title, date=str(parsed.publish_date), content_chars=len(parsed.content),
                               content_sha256=hashlib.sha256(parsed.content.encode()).hexdigest(),
                               image_references=re.findall(r"https?://[^\s]+\.(?:jpg|jpeg|png|gif|webp)(?:\?[^\s]*)?", parsed.content),
                               parser_accepted=True)
                except ValueError as exc:
                    row.update(parser_accepted=False, reason=str(exc))
            records.append(row)
            audit.save_json(output / "spot-results.json", records)
        url = "https://spxy.jlu.edu.cn/bksjy/jxxx.htm"
        result = {"url": url, "time": audit.now(), "ok": False}
        try:
            await fetch.check_robots(url)
            await fetch.fetcher.validate_url(url)
            async with fetch.fetcher.client.stream("GET", url) as response:
                response.raise_for_status()
                if response.is_redirect:
                    raise RuntimeError("Encoding probe does not follow redirects")
                raw = bytearray()
                async for part in response.aiter_bytes():
                    raw.extend(part)
                    if len(raw) > fetch.fetcher.max_bytes:
                        raise RuntimeError("Encoding response exceeded configured size limit")
                raw = bytes(raw)
                digest = hashlib.sha256(raw).hexdigest()
                path = output / "raw" / f"{digest}.bin"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
                result.update(ok=True, status=response.status_code, content_type=response.headers.get("content-type"),
                              response_encoding=response.encoding, meta=[m.decode("ascii", errors="replace") for m in re.findall(rb"<meta[^>]*charset[^>]*>", raw[:8192], re.I)],
                              sha256=digest, raw_path=path.relative_to(output).as_posix(), bytes=len(raw),
                              literal_utf8_replacement_sequences=raw.count(b"\xef\xbf\xbd"))
                try:
                    decoded = raw.decode("utf-8", errors="strict")
                    result.update(strict_utf8_ok=True, replacement_characters=decoded.count("\ufffd"))
                except UnicodeDecodeError as exc:
                    result.update(strict_utf8_ok=False, decode_error=str(exc))
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
        audit.save_json(output / "encoding.json", result)
        print(json.dumps({"samples": len(records), "accepted": sum(r.get("parser_accepted", False) for r in records),
                          "raw_encoding": result}, ensure_ascii=False))
    finally:
        await fetch.close()


if __name__ == "__main__":
    asyncio.run(main())
