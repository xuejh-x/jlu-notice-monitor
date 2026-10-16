"""Verify preservation and emit the complete bounded B7 report and ledgers."""
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
import csv
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit

os.environ["JLU_DATABASE_URL"] = "sqlite://"
from app.services.normalization import canonicalize_url, normalize_title

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/jlu-fix-b7"
FINAL = OUT / "review-guarded-20261015"
CAPTURES = OUT / "recruitment-20261015"
REFERENCES = {"SINGLE_ARTICLE_REFERENCE", "STATIC_RECRUITMENT_INFORMATION_PAGE", "EXTERNAL_PLATFORM_REFERENCES"}
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def csv_out(path, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in r.items()} for r in rows)
    with path.open(encoding="utf-8-sig", newline="") as f:
        assert len(list(csv.DictReader(f))) == len(rows)


def cell(value):
    return str(value or "").replace("|", "／").replace("\n", " ")


def blocked_cause(record):
    message = record.get("error", "")
    for token in ["ROBOTS_DISALLOWED", "TLS_CERTIFICATE_VERIFY_FAILED", "ACCESS_RESTRICTED_HTTP_403", "ACCESS_RESTRICTED_HTTP_429", "ACCESS_RESTRICTED_HTTP_401"]:
        if token in message:
            return token
    if "UNEXPECTED_EOF" in message or "SSLEOFError" in message:
        return "TLS_EOF_CONNECTION_CLOSED"
    if "Server disconnected" in message:
        return "SERVER_DISCONNECTED"
    if "Timeout" in message:
        return "TIMEOUT"
    if record.get("status") == 404:
        return "HTTP_404"
    return "AUTH_REQUIRED" if record.get("auth") else "ACCESS_OTHER"


def issue_tags(row):
    issues = {i for d in row["details"] for i in d.get("comparison", {}).get("issues", [])}
    issues.update(d["reason"] for d in row["details"] if d.get("reason"))
    if row.get("database_replay", {}).get("unexpected_merge_requires_review"):
        issues.add("SAME_TITLE_PUBLICATIONS_REQUIRE_IDENTITY_REVIEW")
    if row["verdict"] == "ACCESS_BLOCKED":
        issues.add(blocked_cause(row["response"]))
    if row["verdict"] == "LIST_OR_PAGINATION_UNSUPPORTED" and "dbzx.jlu.edu.cn" in row["url"]:
        issues.add("MALFORMED_HEADER_ANCESTOR_CONTAINS_NOTICE_LIST")
    if "acib.jlu.edu.cn" in row["url"] and "DATE_NOT_INDEPENDENTLY_VERIFIED" in issues:
        issues.add("UPLOAD_TIME_PUBLICATION_UNCONFIRMED")
    if row["verdict"] == "PERMISSION_RESTRICTED":
        issues.add("COLUMN_PERMISSION_REQUIRED")
    return sorted(issues)


def main():
    now = datetime.now(timezone(timedelta(hours=8))).isoformat()
    prep, baseline, final_tests = [read(OUT / name) for name in ["preparation.json", "baseline-manifest.json", "final-manifest.json"]]
    for group in ["protected_hashes", "prior_reports", "protected_b6"]:
        for p, digest in prep[group].items():
            assert sha(ROOT / p) == digest, p
    for p, digest in prep["inputs"].items():
        assert sha(OUT / p) == digest
    assert sha(ROOT / "backend/config/sources.yaml") == prep["formal_yaml_sha256"]
    for p, digest in final_tests["source_hashes"].items():
        if p.startswith(("backend/app/", "backend/config/", "backend/tests/")):
            assert sha(ROOT / p) == digest, p
    changes = sorted(p for p, digest in final_tests["source_hashes"].items() if p.startswith("backend/app/") and baseline["source_hashes"].get(p) != digest)
    assert changes == ["backend/app/parsers/html.py", "backend/app/services/deduplication.py", "backend/app/services/list_pagination.py", "backend/app/sources/generic.py"]
    patch = []
    for name in changes:
        before = Path(baseline["isolated_backend"]) / Path(name).relative_to("backend")
        patch.extend(difflib.unified_diff(before.read_text(encoding="utf-8").splitlines(True), (ROOT / name).read_text(encoding="utf-8").splitlines(True), fromfile="B7 baseline/" + name, tofile="B7 final/" + name))
    (OUT / "application-changes.diff").write_text("".join(patch), encoding="utf-8")
    assert subprocess.run(["git", "diff", "--quiet", "--", "frontend"], cwd=ROOT).returncode == 0
    rows, summary = read(FINAL / "results.json"), read(FINAL / "summary.json")
    targets = read(CAPTURES / "validation-targets.json")
    assert len(rows) == len(targets) == 116
    assert {r["url"] for r in rows} == {r["url"] for r in targets}
    assert summary["http_attempts"] == summary["application_db_connections"] == summary["downloads"] == summary["oa_requests"] == 0
    for p, digest in read(FINAL / "code-manifest.json")["files"].items():
        path = CAPTURES / p.removeprefix("input/") if p.startswith("input/") else ROOT / p
        assert sha(path) == digest, p
    captures = read(CAPTURES / "requests.json")
    snapshots = 0
    for r in captures.values():
        assert urlsplit(r["url"]).hostname != "oa.jlu.edu.cn"
        assert not re.search(r"\.(?:pdf|docx?|xlsx?|zip|rar|png|jpe?g)$|/download\.jsp$", urlsplit(r["url"]).path, re.I)
        if r.get("html_path"):
            assert sha(CAPTURES / r["html_path"]) == r["sha256"]
            snapshots += 1
    tests = {"baseline": "533 passed, 1 skipped", "regression-before": "5 failed, 399 passed", "regression-before-wordpress-identity": "5 failed, 406 passed", "targeted": "424 passed", "final": "567 passed, 1 skipped"}
    for label, result in tests.items():
        assert result in (OUT / (label + "-tests.log")).read_text(encoding="utf-8"), label
    assert not any("OFFLINE_URL_NOT_CAPTURED" in str(r) for r in rows)
    assert not any(r.get("missing_reference_urls") or r.get("unexpected_urls") for r in rows)
    original = [r for r in rows if not r["id"].startswith("recruitment-")]
    assert len(original) == 112
    matrix, candidates = [], []
    for row in rows:
        issues = issue_tags(row)
        reason = "; ".join(issues) or row["reason"]
        entry = {"id": row["id"], "institution": row["institution"], "column": row["column"], "url": row["url"],
            "priority": row.get("priority", "P3"), "original_status": row["old_status"], "original_issues": row["old_issues"],
            "status": row["status"], "verdict": row["verdict"], "reason": reason,
            "capture_time": row.get("response", {}).get("time"), "review_time": row["checked_at"],
            "http_status": row.get("response", {}).get("status"), "final_url": row.get("response", {}).get("final_url"),
            "list_pages": len(row["pages"]), "list_items": row.get("list_count", 0), "details": len(row["details"]),
            "verified_details": sum(d["verified"] for d in row["details"]), "issues": issues,
            "discovery_url": row["discovery_url"], "evidence_file": f"docs/jlu-fix-b7/results/{row['id']}.json",
            "windows_preview": row["verdict"], "cloud_linux": "NOT_VERIFIED", "cloud_feed": "NOT_RETESTED", "installed_desktop": "NOT_RETESTED",
            "attachment_scope": "DOM references only; no endpoint prefix/full downloads", "history_verified": False,
            "isolated_replay": row.get("database_replay", {}).get("mode", "NOT_EXERCISED"), "enabled": False, "formal_admission": False}
        matrix.append(entry)
        save(OUT / "results" / (row["id"] + ".json"), {**row, "summary": entry, "code_manifest": FINAL.relative_to(ROOT).as_posix() + "/code-manifest.json"})
        if row["verdict"] not in REFERENCES:
            candidates.append({"id": row["id"], "institution": row["institution"], "column": row["column"], "url": row["url"],
                "priority": entry["priority"], "enabled": False, "formal_admission": False, "verdict": row["verdict"], "config": row["config"], "evidence_file": entry["evidence_file"]})
    assert all(c["config"]["enabled"] is False and c["config"]["allow_private_network"] is False for c in candidates)
    save(OUT / "admission-matrix.json", matrix)
    save(OUT / "source-candidates.json", candidates)
    csv_out(ROOT / "docs/jlu-b7-compatibility-report.csv", matrix)
    # Discovery remains a separate denominator, including older-priority sites.
    sites = read(OUT / "live-20261015/site-results.json")
    for site in sites:
        response = site.get("response")
        site["current_cause"] = blocked_cause(response) if response and not response.get("ok") else site["verdict"]
        if "lib.jlu.edu.cn" in site["site_url"]:
            site.update(current_cause="DYNAMIC_HTML_SHELL_NO_NOTICE_LINKS", reason="2026-10-13 robots Disallow:/ preserved; 2026-10-15 HTTPS robots 404 then one allowed homepage returned a dynamic shell; no JavaScript/API/captcha/login flow attempted")
        if site["site_url"] == "https://www.jlu.edu.cn/jgsz/yjjg.htm":
            site.update(current_cause="DIRECTORY_SELF_LINK_REPLACEMENT_IDENTIFIED", replacement_site="https://nercgei.jlu.edu.cn/index.htm",
                        replacement_evidence="docs/jlu-fix-b7/supplement-20261015/official-supplement.json")
    save(OUT / "discovery-gap-ledger.json", sites)
    csv_out(OUT / "discovery-gap-ledger.csv", [{"site_url": s["site_url"], "institutions": s["institutions"], "old_status": s["original_state"],
        "current_cause": s["current_cause"], "reason": s["reason"], "capture_time": (s.get("response") or {}).get("time"), "review_time": s["checked_at"],
        "columns": s["columns"], "omitted_hubs": s["omitted_hubs"], "evidence_file": "docs/jlu-fix-b7/discovery-gap-ledger.json"} for s in sites])
    all_units = read(ROOT / "docs/jlu-audit-evidence/units.json")
    linked = defaultdict(list)
    for unit in all_units:
        if unit["site_url"]:
            linked[unit["institution"]].append(unit)
    units = read(OUT / "live-20261015/unknown-units.json")
    for u in units:
        u["initial_matching_review_time"] = u["review_time"]
        u["review_time"] = now
        u.update(known_official_urls=[], independent_site_url_known=False, website_content_confirmed=False, notice_support_confirmed=False)
        known = linked[u["institution"]]
        if known:
            u.update(status="PREVIOUS_SUPPLEMENT_ALREADY_IDENTIFIED_URL", known_official_urls=[r["site_url"] for r in known],
                independent_site_url_known=True, historical_official_basis=known,
                reason="Original empty directory row duplicates a supplemental official URL; keep access/content verification separate")
            u["website_content_confirmed"] = any(urlsplit(r["url"]).hostname == urlsplit(known[0]["site_url"]).hostname and r.get("response", {}).get("ok") for r in original)
        if u["institution"] == "吉林大学出版社有限责任公司":
            url = "https://press.jlu.edu.cn/lxwm/rczp.htm"
            r = captures[url]
            assert "吉林大学出版社有限责任公司" in (CAPTURES / r["html_path"]).read_text(encoding="utf-8")
            u.update(status="OFFICIAL_WEBSITE_SELF_IDENTITY_CONFIRMED", known_official_urls=["https://press.jlu.edu.cn/index.htm"], independent_site_url_known=True,
                website_content_confirmed=True, response=r, reason="Official contact/profile and legal entity footer match; recruitment page is static contact information, not a supported notice list")
        if u["institution"] == "行政服务中心":
            u.update(status="SHARED_OFFICIAL_UNIT_PAGE_CONFIRMED", known_official_urls=["https://pro.jlu.edu.cn/xzfwzx.htm"], website_content_confirmed=True,
                response=captures["https://pro.jlu.edu.cn/xzfwzx.htm"], reason="Observed university office link and fetched description confirm a shared official unit page; no independent website or public notice column inferred")
        if u["institution"] in {"东荣学院", "莱姆顿学院", "应用技术学院", "吉林吉大控股有限公司", "吉林吉大致远资产经营有限公司"}:
            u["additional_basis"] = [s for s in read(OUT / "supplement-20261015/official-supplement.json") if s["institution"] == u["institution"]]
            u["reason"] += "; targeted primary-site search found associated news/disclosure only, not an independent website"
    save(OUT / "unknown-unit-ledger.json", units)
    csv_out(OUT / "unknown-unit-ledger.csv", units)
    inventory = [{"record_type": "site", "institution": " / ".join(s["institutions"]), "url": s["site_url"], "discovery_url": s["discovery_urls"],
                  "basis": "original official inventory; only designated gap sites rechecked in B7", "support_status": "NOT_IMPLIED_BY_INVENTORY"} for s in read(ROOT / "docs/jlu-audit-evidence/sites.json")]
    supplements = read(OUT / "supplement-20261015/official-supplement.json")
    for s in supplements:
        if s["kind"] == "site_identity":
            inventory.append({"record_type": "site", "institution": s["institution"], "url": s["home_response"]["final_url"], "discovery_url": s["url"],
                "basis": s["basis"], "support_status": "IDENTITY_ONLY_NOTICE_SUPPORT_NOT_IMPLIED"})
    for u in units:
        inventory.append({"record_type": "institution_gap", "institution": u["institution"], "url": u["known_official_urls"], "discovery_url": u["discovery_url"],
            "basis": u["reason"], "support_status": u["status"]})
    for r in matrix:
        inventory.append({"record_type": "column_or_reference", "institution": r["institution"], "url": r["url"], "discovery_url": r["discovery_url"], "basis": r["reason"], "support_status": r["verdict"]})
    csv_out(ROOT / "docs/jlu-b7-site-inventory.csv", inventory)
    # Duplicate candidates are observations, never production merge commands.
    by_url, by_title = defaultdict(list), defaultdict(list)
    for label, scope in [("B7", rows), ("B6", read(ROOT / "docs/jlu-fix-b6/review-accepted-20261015/results.json"))]:
        for row in scope:
            for item in row.get("items", []):
                entry = {"batch": label, "column_url": row["url"], "url": item["url"], "title": item["title"], "date": item.get("publish_date")}
                by_url[canonicalize_url(item["url"])].append(entry)
                if item.get("publish_date") and len(normalize_title(item["title"])) >= 8:
                    by_title[(normalize_title(item["title"]), item["publish_date"])].append(entry)
    same = [v for v in by_url.values() if len({e["column_url"] for e in v if e["batch"] == "B7"}) > 1]
    titles = [v for v in by_title.values() if len({canonicalize_url(e["url"]) for e in v if e["batch"] == "B7"}) > 1]
    cross = [v for v in by_url.values() if {e["batch"] for e in v} == {"B6", "B7"}]
    save(OUT / "duplicate-candidates.json", {"b7_same_url_groups": same, "b7_title_date_candidates": titles, "cross_b6_b7_same_url_groups": cross, "production_merges": 0})
    before = {r["id"]: r for r in read(OUT / "review-1-20261015/results.json")}
    identity = [{"id": r["id"], "url": r["url"], "before": before[r["id"]].get("database_replay"), "after": r.get("database_replay"),
        "samples": [{"url": d["url"], "title": d.get("parsed", {}).get("title"), "date": d.get("parsed", {}).get("publish_date"), "sha256": d.get("response", {}).get("sha256")} for d in r["details"]]}
        for r in original if r["url"] in {"http://nlshm-lab.jlu.edu.cn/yjsjy/zsxx.htm", "http://iamp.jlu.edu.cn/rcpy/zsxx.htm", "https://ywc.jlu.edu.cn/xyggwsgl1/tzgg.htm", "http://ghb.jlu.edu.cn/rczp/zpxx.htm"}]
    save(OUT / "identity-cases.json", identity)
    stages = ["live-20261015", "supplement-20261015", "followup-1-20261015", "followup-2-20261015", "followup-3-20261015", "recruitment-20261015"]
    attempts = sum(read(OUT / stage / "summary.json")["http_attempts_process"] for stage in stages)
    http_records = []
    for stage in stages:
        path = OUT / stage / "http.jsonl"
        if path.exists():
            http_records.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    assert not any(urlsplit(r["url"]).hostname == "oa.jlu.edu.cn" for r in http_records)
    assert not any(urlsplit(r.get("final_url", "")).hostname == "oa.jlu.edu.cn" or "oa.jlu.edu.cn" in r.get("error", "") for r in captures.values())
    group = Counter(r["verdict"] for r in rows)
    unknown_group = Counter(u["status"] for u in units)
    pending = [m for m in matrix if m["verdict"] in {"SAMPLE_REVIEW_REQUIRED", "ACCESS_BLOCKED", "PERMISSION_RESTRICTED", "LIST_OR_PAGINATION_UNSUPPORTED", "HOMEPAGE_SCOPE_REVIEW", "EXTERNAL_PLATFORM_REFERENCES"}]
    save(OUT / "pending-issues.json", pending)
    acceptance = {"time": now, "status": "B7_complete_bounded_audit_repairs_and_ledgers_delivered_external_limits_retained",
        **summary, "original_p3_entries": len(original), "new_entries": 4, "old_failures": dict(Counter(r["verdict"] for r in original if r["old_status"] == "失败")),
        "candidate_configs": len(candidates), "all_candidates_disabled": True, "full_environment_admissions": 0,
        "discovery_gaps_rechecked": len(sites), "original_unreachable_rechecked": sum(s["original_state"] == "unreachable" for s in sites),
        "original_no_column_rechecked": sum(s["original_state"] == "no_column_discovered" for s in sites), "unknown_unit_rows": len(units), "unknown_unit_labels": len({u["institution"] for u in units}),
        "unknown_unit_statuses": dict(unknown_group), "official_site_inventory_urls": len([s for s in inventory if s["record_type"] == "site"]),
        "official_site_inventory_hosts": len({urlsplit(s["url"]).hostname for s in inventory if s["record_type"] == "site"}),
        "new_official_sites": 2, "tests": tests, "http_attempts_total": attempts, "cached_requests": len(captures), "snapshot_hash_checks": snapshots,
        "b7_same_url_groups": len(same), "b7_title_date_candidates": len(titles), "cross_b6_b7_same_url_groups": len(cross),
        "protected_original_files": len(prep["protected_hashes"]), "protected_b6_files": len(prep["protected_b6"]), "prior_reports_preserved": len(prep["prior_reports"]),
        "formal_yaml_sha256": prep["formal_yaml_sha256"], "application_changes": changes, "frontend_changed": False,
        "production_db_connections": 0, "oa_requests": 0, "complete_downloads": 0, "cloud_deployed": False, "github_pushed": False, "client_installed": False}
    save(OUT / "acceptance.json", acceptance)
    save(OUT / "tooling-iterations.json", {"fixture_generator": "Initial regeneration compared Windows-normalized text to mixed source line endings; preserved fixture SHA/source SHA instead. Two failed generation attempts and collection error were tooling issues, not website failures.",
        "offline_stages": "Missing samples and a stopped WordPress pagination boundary remained unadmitted until literal-link HTML follow-up and stricter final review; intermediate runs preserved.",
        "discovery_priority": "Two newly discovered college recruitment entries corrected from initial P3 tooling default to P2; original B6 164-entry scope unchanged.",
        "new_recruitment_references": "Three static descriptions classified after real page review; not marked supported or empty."})
    lines = ["# 吉林大学网站适配修复 B7 报告", "", f"验收时间：{now}。完整 B7 有界交付；保留所有外部阻塞及未验证能力。", "",
        "本轮复核全部 112 个原 P3 入口，并从已保存官方页面补发现 4 个‘人才招聘’入口，共 116 个。59 个发现缺口（15 个原受阻、44 个原未发现栏目）与 308 条原始无官网行另建台账，范围重叠，不相加计算覆盖率。没有正式启用来源、触碰正式 SQLite、部署 Cloud、推送 GitHub、发布或安装客户端。OA 按用户要求零请求。", "",
        "## 1. 实际数量与能力边界", "", "| 指标 | 数量 |", "| --- | ---: |", f"| 原 P3 入口 / 新发现入口 | 112 / 4 |",
        f"| 样本通过，仍有能力限制 | {group['BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN']} |", f"| 样本仍待修复或缺少可靠元信息 | {group['SAMPLE_REVIEW_REQUIRED']} |",
        f"| 访问受阻 / 栏目权限受限 | {group['ACCESS_BLOCKED']} / {group['PERMISSION_RESTRICTED']} |", f"| 列表模板仍不支持 | {group['LIST_OR_PAGINATION_UNSUPPORTED']} |",
        f"| 有零记录证据的当前空栏目 | {group['VERIFIED_EMPTY_COLUMN']} |", f"| 单篇文章 / 静态招聘说明 / 外部平台引用 | {group['SINGLE_ARTICLE_REFERENCE']} / {group['STATIC_RECRUITMENT_INFORMATION_PAGE']} / {group['EXTERNAL_PLATFORM_REFERENCES']} |",
        f"| 混合首页，范围待确认 | {group['HOMEPAGE_SCOPE_REVIEW']} |", f"| 完全通过全部运行环境 / 正式准入 | 0 / 0 |", f"| 独立禁用候选配置 | {len(candidates)} |",
        f"| 列表页记录 / 按栏目去重的列表通知记录 | {summary['list_pages']} / {summary['list_items']} |", f"| 详情样本 / 四项独立对照通过 | {summary['details']} / {summary['verified_details']} |",
        f"| 两轮隔离稳定性回放通过 | {summary['isolated_replays']} |", f"| HTTP 发起尝试 / 逻辑缓存条目 / HTML 哈希检查 | {attempts} / {len(captures)} / {snapshots} |",
        f"| 新增有官方依据站点 / 合并库存 URL / 库存主机 | 2 / {acceptance['official_site_inventory_urls']} / {acceptance['official_site_inventory_hosts']} |", "",
        "每栏目最多两页、三篇详情；不足三篇全检。部分正文只是附件或图片引用，端点下载、OCR、全历史均未验证。‘样本通过’需要列表独立召回对照、标题、日期、正文、附件 DOM 对照、分页边界及隔离重放，HTTP 200 或非空不能单独通过。隔离重放使用已经解析的样本，生产策略与真正 Cloud/feed、已安装 Desktop fallback 并未实跑。", "",
        "所有 116 个入口均有范围/访问/预览结论；15 个引用对象无需作为独立列表适配，3 个混合首页没有确定监控范围。剩余适配对象中没有因为未取到样本而伪报通过。59 个发现入口全部完成限定深度检查，但未发现栏目不等于没有通知。", "",
        "## 2. 本批实际修复", "",
        "- VSB 文章标题、发布日期：修复已观察的 content-bt、ti/author、readtitle、item_biaoti、biaoti、#Title、表格 pubtime_publisher、匿名居中元信息及 view-title/view-info。只在文章范围、正文之前读取；正文事件日期与缺少的发布日期不补造。nav01 只为有明确文章标题/时间结构且无菜单链接的模板读取元信息，普通导航仍被排除。",
        "- 表格与定义列表复用现有高级选择器：附属中学、边疆考古、哲学基础理论、高教所均有独立候选，未为各站新增专用爬虫。哲学列表显示日期与静态属性可能不一致，详情日期未出现仍保留未确认。",
        "- WordPress 复用规则：只读取 article.type-post 的正文、文章头标题与 ISO datetime；只提取同一文章中带‘相关附件:N’标题的附件列表，不混入网站页脚、分类或标签。附件仅引用，不下载。",
        "- WordPress 有界分页：支持同源同栏目 /page/正整数，保留稳定查询参数校验；跨栏目、跨站、认证信息、HTTP 降级、伪数字与路径逃逸继续拦截。审计拒绝把 NEXT_PAGE_OUTSIDE_COLUMN 等安全停止误算分页通过；第二页已真实补证。",
        "- 招生通知误合并：复试名单与拟录取名单、普通公示与显式第二批分别保留；URL/public_id 优先级、14 天窗口、0.92 阈值、来源关系和用户状态不变。两组真实样本回放由 2 条恢复为 3 条独立记录，第二轮没有重复新增。没有批量修正正式旧数据。",
        "- 栏目发现：修复‘人才招聘’标签遗漏。缓存内发现并检查人才办、经济学院、交通学院、出版社四个明确入口；经济学院样本通过，其余三个是长期招聘/联系说明页。静态说明不标为已支持列表。",
        "- 审计对照纠正：资产处侧栏新闻不再计入当前栏目召回；原 11 个单篇文章引用独立分类，其中 8 个旧 JSP 引用当前权限受限仍保留限制。3 个首页不按混合新闻强行准入。", "",
        "可复用代码差异见 [application-changes.diff](jlu-fix-b7/application-changes.diff)，实际四个应用文件有变化；source preview、安全校验、执行策略、数据库模型和 UI 未变更。", "",
        "## 3. 发现缺口与机构官网补证", "",
        "四个官方目录、学校主页本轮重新取得快照；59 个指定入口各首页加至多三个明确相关一级入口，遗漏的更深入口逐条保存。8 次定向检索只接受官方原页补证；外部转载、百科、企业聚合与冒用学校内容的博彩站未纳入、未抓取。", "",
        "原受阻 15 个入口：10 个 TLS EOF 提前关闭（不同于证书有效期失败）、第一医院服务器断连、理论法学站超时、附中实验学校证书验证失败、图书馆动态空壳、OA 暂缓，各保留完整错误链。robots 获取受阻时没有继续正文请求；确定性证书问题未关闭验证。", "",
        "图书馆历史 robots 的 Disallow:/ 原文保留。本轮 HTTPS robots 为 404，按当前可观察规则只获取一次首页；页面是动态空壳，未执行脚本或猜测 API、未绕过访问控制，仍没有已验证通知栏目。不能沿用旧 robots 结论假装从未复核，也不能据首页 200 宣称支持。", "",
        "补证两个官网：吉林大学出版社 https://press.jlu.edu.cn/index.htm（联系页、简介和‘吉林大学出版社有限责任公司’页脚自证）；国家地球物理探测仪器工程技术研究中心 https://nercgei.jlu.edu.cn/index.htm（中心简介明确依托吉林大学）。后者原官方目录链接回研究机构目录，本次记录正确站点作为替代发现依据，不把两站 URL 当作协议别名强合并。", "",
        "原始 units.json 确有 308 条 site_url 为空、298 个不同名称，其中附中、附小、附中实验学校 3 条在补充记录已有 URL。因此旧摘要 305 与原始空行口径不同，本轮同时保存两者，不覆盖历史。298 个名称也不等于 298 个独立单位，重复‘综合办公室’等不凭名称合并。", "",
        f"机构行处理结果：{dict(unknown_group)}。出版社官网已自证；行政服务中心确认是校长办公室共享页面，未推断独立站点。附中实验学校仅 URL 已知、证书受阻；东荣/莱姆顿/应用技术学院和两家校管企业的补充官方新闻/公开信息没有证明独立官网。其他条目均保留各自目录 URL、时间与未找到官方链接的限定原因，未执行 308 次独立全网查询。", "",
        "逐行记录见 [unknown-unit-ledger.csv](jlu-fix-b7/unknown-unit-ledger.csv)、[discovery-gap-ledger.csv](jlu-fix-b7/discovery-gap-ledger.csv)、[新增库存](jlu-b7-site-inventory.csv)。原 44 个缺口中学工、创新创业通知现可从首页发现，但属于已有候选，不重复计为新栏目。", "",
        "## 4. 仍未解决的原因与优先级", "",
        "- P0：本批完整后端回归通过；OA 按用户要求暂缓，截图‘部分失败’与系统网络问题不在本批恢复。真实 Cloud/feed、已安装客户端状态仍另行验收。",
        "- P1：服务器/TLS/robots 前置条件受阻的管理服务入口等待可访问环境或站点修复；缺少发布日期与重复发布语义不得通过猜测时间或放宽去重消除。正式来源准入仍需独立范围。",
        "- P2：附属中学、高教所等特殊列表已恢复；新发现经济学院人才招聘样本通过。交通学院长期招聘说明没有按通知列表启用。各批学院剩余限制继续保留 B6 报告。",
        "- P3：哲学中心、廉政、集成光电子三栏、汽车底盘实验室缺少可靠发布日期或仅有上传时间；医院/理论化学旧镜像包含乱码，医院附件是带损坏文本的 Teleport JavaScript 入口，不执行脚本恢复文件。",
        "- P3：东北振兴页面错误闭合使通知列表落在 header 祖先内；现有导航保护正确拒绝。需站点修复 DOM 或另行实现带可审查安全边界的专门规则，不能全局放行 header。智能仪器四条通知全指向微信，未抓外部平台。",
        "- P3：数量经济旧 list.php?SID=1 仍 404；同一官方首页明确链接的新 /xgxw1/zxtz.htm 已独立验证，旧地址不重试、不假称重定向已修好。后勤集团、测试中心旧列表明确权限受限，不登录。",
        "- 重复候选：医院传染病两条同标题/日期/正文，可能为原站重复发布；人兽共患病 2017 招聘同名但正文版本不同，需人工确定转载/修订身份。保留 URL、正文哈希和关系，不在正式库合并或拆分。", "",
        f"B7 栏目间同 URL 组 {len(same)}，不同 URL 同标题/日期候选组 {len(titles)}；与 B6 快照共有 URL 组 {len(cross)}。这是跨栏目引用/转载候选，不能当成数据库重复通知数量。", "",
        "## 5. 逐栏结论（含全部旧失败）", "", "| 机构 / 栏目 | 原状态 | 当前结论 | 原因或剩余问题 | 证据 |", "| --- | --- | --- | --- | --- |"]
    for r in matrix:
        lines.append(f"| {cell(r['institution'])} / [{cell(r['column'])}]({r['url']}) | {cell(r['original_status'])} | {cell(r['verdict'])} | {cell(r['reason'])} | [{r['id']}](jlu-fix-b7/results/{r['id']}.json) |")
    lines += ["", "## 6. 复现、回归与保留证明", "", "最终逐栏 CSV：[jlu-b7-compatibility-report.csv](jlu-b7-compatibility-report.csv)；每行 JSON 包含请求 URL、实际时间、最终 URL、错误链、样本、正文/附件对照、分页、两轮内存库结果和代码清单。缓存为解码后的 HTML 证据，原始响应字节与完整文件未保存。", "",
        "离线复现（零网络）：", "", "```powershell", ".\\backend\\.venv\\Scripts\\python.exe backend/scripts/review_jlu_b7.py --input docs/jlu-fix-b7/recruitment-20261015 --output docs/jlu-fix-b7/reproduce-new-directory", "```", "",
        "该命令只读本批快照，缺少 URL 立即失败；改变代码需新输出目录，不能覆盖既有验收。线上采集脚本有逐条 checkpoint 和代码指纹，断点继续使用原缓存而不重试已确定限制。", "",
        "| 检查 | 真实结果 |", "| --- | --- |", *[f"| {label} | {value} |" for label, value in tests.items()], "",
        "最终完整后端 567 通过、1 跳过；跳过为未配置的外部 PostgreSQL 集成验证，没有连接外部数据库。针对性 424 通过，最后四项栏目发现/元信息位置边界测试由完整回归覆盖；完整回归已包含全部 34 个新增测试。前端未变更，因此未重复前端 test/lint/build。", "",
        f"原 1449 份受保护证据、{len(prep['protected_b6'])} 份 B6 文件及 9 份既有报告 SHA 均未变化；正式 sources.yaml SHA 为 `{prep['formal_yaml_sha256']}`。程序全局数据库连接被拒绝，样本回放与 pytest 仅使用隔离数据。候选全部 disabled，Cloud/Desktop 策略与用户 ID、已读、收藏、来源关系保持。", "",
        "测试生成器曾遇到 Windows 换行再生成校验误报，已改用既存 fixture/source SHA 保护；保留 collection 日志及 tooling-iterations.json。这些不是学校站点失败。原始首轮及各次离线结果均保留，未把中间缺少缓存的结果纳入最终失败统计。", "",
        "B6 与 B7 两个大板块已分别交付；下一阶段应按需要选择正式来源准入、Cloud/feed 实机验收或外部站点条件恢复后复核。本轮停在 B7，不自动部署、补全历史、修改系统网络或更新客户端。", ""]
    (ROOT / "docs/JLU_SITE_FIX_B7_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    report = ROOT / "docs/JLU_SITE_FIX_B7_REPORT.md"
    local_links = [url for url in re.findall(r"\]\(([^)]+)\)", report.read_text(encoding="utf-8")) if not url.startswith(("http://", "https://"))]
    assert all((report.parent / url).is_file() for url in local_links)
    save(OUT / "delivery-verification.json", {"time": now, "local_report_links_verified": len(local_links), "http_response_records_checked": len(http_records),
        "oa_response_records": 0, "csv_rows": {"compatibility": len(matrix), "unknown_institutions": len(units), "discovery_gaps": len(sites), "inventory": len(inventory)},
        "delivered_files": {p.relative_to(ROOT).as_posix(): sha(p) for p in [report, ROOT / "docs/jlu-b7-compatibility-report.csv", ROOT / "docs/jlu-b7-site-inventory.csv", OUT / "acceptance.json"]}})
    print(json.dumps({"entries": len(rows), "verdicts": dict(group), "candidates": len(candidates), "unknown_statuses": dict(unknown_group), "http_attempts": attempts,
        "protected_b6_files": len(prep["protected_b6"]), "tests": tests["final"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
