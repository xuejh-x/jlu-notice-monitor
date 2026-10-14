"""Inspect two previously discovered public employment columns, serial and read-only."""
from __future__ import annotations
import argparse
import asyncio
from urllib.parse import urljoin, urlsplit
import os
from bs4 import BeautifulSoup
import audit_jlu_sites as audit


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    out = (audit.ROOT / args.output_dir).resolve()
    assert out.is_relative_to(audit.ROOT / "docs/jlu-fix-b4") and out != audit.ROOT / "docs/jlu-fix-b4"
    audit.EVIDENCE = out
    os.environ["JLU_APP_DATA_DIR"] = str(out / "runtime")
    fetch = audit.AuditFetch()
    rows = []
    try:
        for cid in ["jyzp_tzgg", "jyzp_gs"]:
            url = "https://jdjyw.jlu.edu.cn/portal/jyzp/article/list?cid=" + cid
            result = await fetch.get(url)
            row = {k: v for k, v in result.items() if k != "html"}
            row["details"] = []
            if result.get("ok") and not result.get("auth"):
                soup = BeautifulSoup(result["html"], "html.parser")
                anchors = soup.select(".m-list-line_content h3 a[href]")
                for anchor in anchors[:3]:
                    target = urljoin(url, anchor["href"])
                    if urlsplit(target).hostname != "jdjyw.jlu.edu.cn":
                        continue
                    detail = await fetch.get(target)
                    row["details"].append({k: v for k, v in detail.items() if k != "html"})
                    print(target, detail.get("ok"), detail.get("html_path"), flush=True)
            rows.append(row)
            audit.save_json(out / "inspection.json", rows)
    finally:
        await fetch.close()


if __name__ == "__main__":
    asyncio.run(main())
