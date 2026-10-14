"""Create disabled B4 candidates from the official inventory, never production YAML."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]


def main():
    original = json.loads((ROOT / "docs/jlu-audit-evidence/columns.json").read_text(encoding="utf-8"))
    urls = [
        ("xsc", "https://xsc.jlu.edu.cn/index/tzgg.htm"),
        ("employment-notices", "https://jdjyw.jlu.edu.cn/portal/jyzp/article/list?cid=jyzp_tzgg"),
        ("employment-publicity", "https://jdjyw.jlu.edu.cn/portal/jyzp/article/list?cid=jyzp_gs"),
        ("jwc-teaching-publicity", "https://jwc.jlu.edu.cn/list.jsp?urltype=tree.TreeTempUrl&wbtreeid=1402"),
        ("jwc-certificates", "https://jwc.jlu.edu.cn/fwzn/xy1/zmsgs.htm"),
        ("yzb-notices", "https://yzb.jlu.edu.cn/index/tzgg.htm"),
        ("yzb-publicity", "https://yzb.jlu.edu.cn/index/lqgs.htm"),
        ("yzb-doctor-notices", "https://yzb.jlu.edu.cn/bszs/zsgg.htm"),
        ("yzb-doctor-publicity", "https://yzb.jlu.edu.cn/bszs/lqgs.htm"),
        ("yzb-master-notices", "https://yzb.jlu.edu.cn/sszs/zsgg.htm"),
        ("yzb-master-publicity", "https://yzb.jlu.edu.cn/sszs/lqgs.htm"),
        ("kjc", "https://kjc.jlu.edu.cn/tzgg.htm"),
        ("hssra", "https://hssra.jlu.edu.cn/tzgg1.htm"),
        ("graduate-school", "https://yjsy.jlu.edu.cn/tzgg.htm"),
        ("youth", "https://youth.jlu.edu.cn/index/tzgg.htm"),
        ("international", "http://cie.jlu.edu.cn/ggtz.htm"),
        ("defense-conditional", "https://yjs.jlu.edu.cn/gsapp/sys/dbgsglappecupl/*default/index.do"),
        ("continuing-conditional", "https://dec.jlu.edu.cn/html/tzgg1"),
        ("continuing-academic-conditional", "https://dec.jlu.edu.cn/html/xljy/tzgg"),
    ]
    candidates = []
    for code, url in urls:
        row = next(r for r in original if r["column_url"] == url)
        config = {"code": "candidate-jlu-" + code, "name": row["institution"] + " / " + row["column"],
                  "base_url": url, "parser": "generic_html", "enabled": False,
                  "auth_type": "none", "allow_private_network": False,
                  "validation_scope": "local", "execution_policy": "cloud_preferred", "parser_config": {"pagination_limit": 1}}
        if code.startswith("employment"):
            config["parser_config"].update(item_selector=".m-list-line_content", title_selector="h3 a[title]",
                                           url_selector="h3 a[href*='/portal/jyzp/article/details?id=']", time_selector="span:last-child")
        candidates.append({"id": code, "institution": row["institution"], "column": row["column"], "priority": row["priority"],
                           "discovery_url": row["discovery_url"], "discovery_basis": row["discovery_basis"],
                           "scope": "only this public column; first page; no history/cloud admission",
                           "conditional": code.endswith("conditional"), "support_status": "DRAFT_UNVERIFIED_DISABLED", "config": config})
    out = ROOT / "docs/jlu-fix-b4"
    out.mkdir(parents=True, exist_ok=True)
    for name in ["source-candidates.json", "source-candidates.yaml"]:
        if (out / name).exists():
            raise RuntimeError("Candidates already exist; review changes instead of overwriting")
    (out / "source-candidates.json").write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "source-candidates.yaml").write_text(yaml.safe_dump({"candidate_sources_only": candidates}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    assert hashlib.sha256((ROOT / "backend/config/sources.yaml").read_bytes()).hexdigest() == "d0c9f5af9f7e7477a6803d5f564904d0d9d86d75938f7a76d592da380e496c6d"
    print(f"Prepared {len(candidates)} disabled candidates; production configuration unchanged")


if __name__ == "__main__":
    main()
