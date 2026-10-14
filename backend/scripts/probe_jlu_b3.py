"""Serial, resumable public attachment prefix checks; no downloads or DB writes."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import csv
import hashlib
import os
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

import audit_jlu_sites as audit
from app.parsers import parse_detail_html
from app.schemas.notice import NoticeCandidate
from app.services.attachment_validation import classify_attachment_prefix
from app.services.http_diagnostics import exception_summary
from app.sources.oa_public import OAPublicSource, parse_oa_attachment_references


class PrefixAudit(audit.AuditFetch):
    async def probe(self, url, kind):
        key = "b3-prefix:" + url
        if key in self.cache:
            return self.cache[key]
        result = {"url": url, "time": audit.now(), "method": "GET Range bytes=0-4095", "expected_type": kind,
                  "complete_download_verified": False, "attempts": []}
        for attempt in range(2):
            current = url
            status = 0
            start = len(self.responses)
            try:
                visited = set()
                for _ in range(4):
                    if current in visited:
                        raise RuntimeError("REDIRECT_LOOP")
                    visited.add(current)
                    await self.fetcher.validate_url(current)
                    async with self.fetcher.client.stream("GET", current, headers={"Range": "bytes=0-4095"}) as response:
                        status = response.status_code
                        result.update(status=status, final_url=str(response.url), content_type=response.headers.get("content-type", ""),
                                      disposition=response.headers.get("content-disposition", ""))
                        if response.is_redirect:
                            location = response.headers.get("location", "")
                            if not location:
                                raise RuntimeError("REDIRECT_WITHOUT_LOCATION")
                            target = urljoin(current, location)
                            if any(token in urlsplit(target).path.lower() for token in ("login", "/sso", "/auth")):
                                result.update(category="AUTH_REQUIRED", file_prefix_verified=False, reason="Redirect leads to authentication; not followed")
                                break
                            current = target
                            continue
                        prefix = bytearray()
                        async for chunk in response.aiter_bytes(chunk_size=1024):
                            prefix.extend(chunk[:4096 - len(prefix)])
                            if len(prefix) >= 4096:
                                break
                        prefix = bytes(prefix)
                        digest = hashlib.sha256(prefix).hexdigest()
                        path = audit.EVIDENCE / "prefix" / f"{digest}.bin"
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(prefix)
                        result.update(prefix_path=path.relative_to(audit.EVIDENCE).as_posix(), prefix_sha256=digest)
                        result.update(classify_attachment_prefix(status, response.headers, prefix, kind))
                        break
                else:
                    raise RuntimeError("REDIRECT_LIMIT")
                result["attempts"].append({"number": attempt + 1, "time": audit.now(), "status": status, "category": result["category"]})
                if status in {502, 503, 504} and attempt == 0:
                    await asyncio.sleep(2)
                    continue
                break
            except Exception as exc:
                records = [r for r in self.responses[start:] if urlsplit(r["url"]).path != "/robots.txt"]
                status = records[-1]["status"] if records else 0
                error = exception_summary(exc)
                category = {401: "AUTH_REQUIRED", 403: "ACCESS_DENIED", 429: "RATE_LIMITED", 404: "NOT_FOUND", 410: "NOT_FOUND"}.get(status)
                if not category:
                    category = "ROBOTS_BLOCKED" if "ROBOTS_" in error else ("URL_SECURITY_REJECTED" if type(exc).__name__ == "UnsafeSourceUrl" else "TRANSPORT_ERROR")
                result.update(status=status, category=category, file_prefix_verified=False, reason=error)
                result["attempts"].append({"number": attempt + 1, "time": audit.now(), "status": status, "category": category})
                if attempt == 0 and (isinstance(exc, httpx.TimeoutException) or status in {502, 503, 504}):
                    await asyncio.sleep(2)
                    continue
                break
        self.cache[key] = result
        audit.save_json(audit.EVIDENCE / "requests.json", self.cache)
        return result


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--only-direct", action="store_true", help="Only two previously discovered direct-file controls; no OA retry")
    args = parser.parse_args()
    output = (audit.ROOT / args.output_dir).resolve()
    assert output.is_relative_to(audit.ROOT / "docs/jlu-fix-b3") and output != audit.ROOT / "docs/jlu-fix-b3"
    audit.EVIDENCE = output
    os.environ["JLU_APP_DATA_DIR"] = str(output / "runtime")
    files = ["backend/app/parsers/html.py", "backend/app/sources/base.py", "backend/app/sources/generic.py",
             "backend/app/sources/oa_public.py", "backend/app/services/attachment_validation.py",
             "backend/app/services/source_security.py", "backend/app/services/tls.py", "backend/scripts/audit_jlu_sites.py", "backend/scripts/probe_jlu_b3.py"]
    fingerprint = {name: hashlib.sha256((audit.ROOT / name).read_bytes()).hexdigest() for name in files}
    previous = audit.load_json(output / "code-manifest.json", {})
    if (output / "requests.json").exists() and (previous.get("files") != fingerprint or previous.get("only_direct") != args.only_direct):
        raise RuntimeError("Probe fingerprint changed; choose a new output directory")
    audit.save_json(output / "code-manifest.json", {"time": audit.now(), "files": fingerprint, "database": "sqlite://", "only_direct": args.only_direct, "mode": "serial public prefix checks, no auth/captcha bypass"})
    fetch = PrefixAudit()
    matrix = []
    articles = []
    controls = [("软件教办图片附件", "https://csw.jlu.edu.cn/info/1095/8548.htm", 6),
                ("计算机学院办公文档", "https://ccst.jlu.edu.cn/info/1056/21217.htm", 1),
                ("教务表格", "https://jwc.jlu.edu.cn/info/1050/12677.htm", 1),
                ("创新创业附件", "https://cxcyjyxy.jlu.edu.cn/info/1060/2351.htm", 1)]
    if args.only_direct:
        controls = [("研究生招生公开 PDF", "https://yzb.jlu.edu.cn/info/1052/3347.htm", 1),
                    ("植物科学公开表格", "https://zky.jlu.edu.cn/info/1022/6178.htm", 1)]
    try:
        for name, url, limit in controls:
            r = await fetch.get(url)
            row = {k: v for k, v in r.items() if k != "html"}
            row["institution"] = name
            if r.get("ok") and not r.get("auth"):
                parsed = parse_detail_html(r["html"], r["final_url"], NoticeCandidate(title=name, url=url))
                row["attachments"] = [a.model_dump() for a in parsed.attachments]
                for attachment in parsed.attachments[:limit]:
                    probe = await fetch.probe(attachment.url, attachment.type)
                    matrix.append(dict(probe, institution=name, article_url=url, filename=attachment.filename, type=attachment.type))
            articles.append(row)
            audit.save_json(output / "articles.json", articles)
            audit.save_json(output / "matrix.json", matrix)
        oa_url = "https://oa.jlu.edu.cn/defaultroot/PortalInformation!getInformation.action?channelId=179577&id=71024221"
        r = await fetch.get(oa_url) if not args.only_direct else {"ok": None, "url": oa_url, "time": audit.now(), "reason": "NOT_CHECKED: direct-file controls only"}
        oa = {k: v for k, v in r.items() if k != "html"}
        oa["encoder_post_exercised"] = False
        if r.get("ok") and not r.get("auth"):
            references = parse_oa_attachment_references(r["html"], oa_url)
            oa["references"] = [{"stored_name": ref.stored_name, "display_name": ref.display_name} for ref in references]
            if references:
                source = OAPublicSource({"code": "oa-audit", "name": "OA Audit", "base_url": "https://oa.jlu.edu.cn"})
                await source.client.aclose()
                source.client = fetch.fetcher.client
                source.retries = 0
                encoder = "https://oa.jlu.edu.cn/defaultroot/rd/download/BASEEncoderAjax.jsp"
                try:
                    await fetch.fetcher.validate_url(encoder)
                    await fetch.check_robots(encoder)
                    oa["encoder_post_exercised"] = True
                    url = await source._attachment_url(references[0], oa_url)
                    ref = references[0]
                    kind = Path(ref.stored_name).suffix.lower().lstrip(".")
                    probe = await fetch.probe(url, kind)
                    matrix.append(dict(probe, institution="OA 公开附件", article_url=oa_url, filename=ref.display_name, type=kind))
                except Exception as exc:
                    oa["encoder_error"] = exception_summary(exc)
        audit.save_json(output / "oa.json", oa)
        audit.save_json(output / "matrix.json", matrix)
        fields = ["institution", "article_url", "url", "filename", "type", "time", "status", "category", "file_prefix_verified",
                  "complete_download_verified", "read_bytes", "prefix_sha256", "prefix_path", "reason"]
        with (output / "attachment-matrix.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(matrix)
        summary = {"time": audit.now(), "article_controls": len(articles), "attachment_endpoints": len(matrix),
                   "categories": dict(Counter(r["category"] for r in matrix)),
                   "file_prefix_verified": sum(r.get("file_prefix_verified", False) for r in matrix),
                   "complete_downloads": 0, "oa_detail_accessible": r.get("ok", False), "oa_post_exercised": oa["encoder_post_exercised"]}
        audit.save_json(output / "summary.json", summary)
        print(summary, flush=True)
    finally:
        await fetch.close()


if __name__ == "__main__":
    asyncio.run(main())
