"""Offline B6 acceptance, candidate inventory and truthful complete-block report."""
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
import csv
import difflib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

os.environ["JLU_DATABASE_URL"] = "sqlite://"
from app.services.normalization import canonicalize_url

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = ROOT / "docs/jlu-fix-b6"
FINAL = OUT / "review-accepted-20261015"
REFERENCES = {"LOGIN_REFERENCE_OA_DEFERRED", "SINGLE_ARTICLE_REFERENCE", "STATIC_INFORMATION_PAGE", "SECTION_DIRECTORY_REFERENCE", "EXTERNAL_REFERENCE_DIRECTORY"}


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def cell(value):
    return str(value).replace("|", "／").replace("\n", " ")


def main():
    now = datetime.now(timezone(timedelta(hours=8))).isoformat()
    preparation = read(OUT / "preparation.json")
    baseline, final = read(OUT / "baseline-manifest.json"), read(OUT / "final-manifest.json")
    for name, digest in final["source_hashes"].items():
        if name.startswith(("backend/app/", "backend/config/", "backend/tests/")):
            assert sha(ROOT / name) == digest, name
    changed = sorted(p for p, digest in final["source_hashes"].items() if p.startswith("backend/app/") and baseline["source_hashes"].get(p) != digest)
    assert changed == ["backend/app/parsers/html.py", "backend/app/services/deduplication.py"]
    for path, digest in preparation["protected_hashes"].items():
        assert sha(ROOT / path) == digest, path
    for path, digest in preparation["prior_reports"].items():
        assert sha(ROOT / path) == digest, path
    for path, digest in preparation["inputs"].items():
        assert sha(ROOT / path) == digest, path
    for path, digest in baseline["source_hashes"].items():
        if path.startswith("backend/config/"):
            assert sha(ROOT / path) == digest, path
    assert subprocess.run(["git", "diff", "--quiet", "--", "frontend"], cwd=ROOT).returncode == 0
    patch = []
    for name in changed:
        before = Path(baseline["isolated_backend"]) / Path(name).relative_to("backend")
        patch.extend(difflib.unified_diff(before.read_text(encoding="utf-8").splitlines(True), (ROOT / name).read_text(encoding="utf-8").splitlines(True), fromfile="B6 baseline/" + name, tofile="B6 final/" + name))
    (OUT / "application-changes.diff").write_text("".join(patch), encoding="utf-8")
    summary, rows = read(FINAL / "summary.json"), read(FINAL / "results.json")
    targets = read(OUT / "targets.json")
    assert len(rows) == 164 and {r["url"] for r in rows} == {t["url"] for t in targets}
    assert summary["http_attempts_this_session"] == summary["application_db_connections"] == summary["oa_requests"] == summary["complete_downloads"] == 0
    for path, digest in read(FINAL / "code-manifest.json")["files"].items():
        actual = OUT / "followup-jsp-20261015" / path.removeprefix("input/") if path.startswith("input/") else ROOT / path
        assert sha(actual) == digest, path
    stages = ["discovery-20261015", "live-20261015", "followup-20261015", "followup-jsp-20261015"]
    network_attempts = sum(read(OUT / stage / "summary.json")["http_attempts_this_session"] for stage in stages)
    followup_details = sum(read(OUT / stage / "summary.json")["new_article_urls"] for stage in stages[2:])
    assert followup_details == 7
    captures = read(OUT / "followup-jsp-20261015/requests.json")
    html_checks = 0
    for record in captures.values():
        assert urlsplit(record["url"]).hostname != "oa.jlu.edu.cn"
        if record.get("html_path"):
            assert sha(OUT / "followup-jsp-20261015" / record["html_path"]) == record["sha256"]
            html_checks += 1
    tests = {"baseline": "487 passed, 1 skipped", "regression-before": "15 failed, 355 passed", "targeted": "394 passed", "final": "533 passed, 1 skipped"}
    for label, result in tests.items():
        assert result in (OUT / (label + "-tests.log")).read_text(encoding="utf-8"), label
    assert all("OFFLINE_URL_NOT_CAPTURED" not in str(d.get("reason", "")) for r in rows for d in r["details"])
    assert not any(r.get("missing_reference_urls") or r.get("unexpected_urls") for r in rows)
    group = Counter(r["verdict"] for r in rows)
    failures = [r for r in rows if r["old_status"] == "失败"]
    assert len(failures) == 30
    pending, candidates, matrix = [], [], []
    for row in rows:
        applicable = row["verdict"] not in REFERENCES
        candidate = {"id": row["id"], "institution": row["institution"], "column": row["column"], "url": row["url"],
                     "scope": "only this public column; <=2 pages, <=3 article samples; no full history/Cloud admission",
                     "discovery_url": row["discovery_url"], "original_evidence": row["original_evidence"],
                     "support_status": row["verdict"], "enabled": False, "formal_admission": False,
                     "config": row["config"] if applicable else None}
        if applicable:
            assert candidate["config"]["enabled"] is False
            candidates.append(candidate)
        detail_issues = sorted({issue for d in row["details"] for issue in d.get("comparison", {}).get("issues", [])})
        errors = sorted({d["reason"] for d in row["details"] if d.get("reason")})
        note = row["reason"]
        if row["verdict"] == "SAMPLE_REVIEW_REQUIRED":
            note = "; ".join(detail_issues + errors) or "Same-title publication/identity candidate requires manual review; no production merge"
            pending.append({"id": row["id"], "institution": row["institution"], "column": row["column"], "url": row["url"], "reason": note,
                            "evidence": f"docs/jlu-fix-b6/results/{row['id']}.json"})
        listing_encoding = row.get("response", {}).get("replacement_chars", 0)
        entry = {"id": row["id"], "institution": row["institution"], "column": row["column"], "url": row["url"],
                 "original_status": row["old_status"], "original_issues": row["old_issues"], "status": row["status"], "verdict": row["verdict"],
                 "capture_time": row.get("response", {}).get("time"), "review_time": row["checked_at"], "reason": note,
                 "list_pages": len(row["pages"]), "list_count": row.get("list_count", 0), "details": len(row["details"]),
                 "verified_details": sum(d["verified"] for d in row["details"]), "listing_replacement_characters": listing_encoding,
                 "publication": "bounded sample verified" if row["details"] and all(d.get("comparison", {}).get("date_verified") for d in row["details"]) else "not confirmed / not applicable",
                 "windows_public_preview": row["verdict"], "cloud_linux": "NOT_VERIFIED", "cloud_feed": "NOT_CONFIGURED_AT_B5_D_NO_RETEST",
                 "desktop_installed_client": "NOT_RETESTED", "incremental": row.get("database_replay", {}).get("mode", "NOT_EXERCISED"),
                 "attachments": "DOM references only; no endpoint downloads in B6", "full_download_verified": False,
                 "enabled": False, "formal_admission": False, "evidence_file": f"docs/jlu-fix-b6/results/{row['id']}.json"}
        matrix.append(entry)
        save(OUT / "results" / (row["id"] + ".json"), {**row, "summary": entry,
             "code_manifest": "docs/jlu-fix-b6/review-accepted-20261015/code-manifest.json",
             "discovery_record": "docs/jlu-fix-b6/discovery-20261015/results.json; match same id", "production_db_connections": 0})
    save(OUT / "source-candidates.json", candidates)
    save(OUT / "admission-matrix.json", matrix)
    save(OUT / "unresolved-capabilities.json", pending)
    with (ROOT / "docs/jlu-b6-compatibility-report.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(matrix[0]))
        writer.writeheader()
        writer.writerows(matrix)
    urls = defaultdict(dict)
    title_dates = defaultdict(dict)
    for row in rows:
        for item in row.get("items", []):
            urls[canonicalize_url(item["url"])][row["id"]] = {"column_url": row["url"], "title": item["title"]}
            if item.get("publish_date"):
                key = item["title"] + " / " + item["publish_date"]
                title_dates[key][canonicalize_url(item["url"])] = {"column_url": row["url"], "url": item["url"]}
    same_url = {u: list(g.values()) for u, g in urls.items() if len(g) > 1}
    same_title = {t: list(g.values()) for t, g in title_dates.items() if len(g) > 1}
    save(OUT / "duplicate-candidates.json", {"time": now, "scope": "bounded list occurrences; not production database duplicates",
         "same_url_cross_column_groups": len(same_url), "same_title_date_different_url_groups": len(same_title), "same_url": same_url, "same_title_date": same_title, "production_merges": 0})
    # Preserve intermediate validation failures as tooling history, not site failures.
    save(OUT / "tooling-iterations.json", {"time": now, "excluded_from_final_site_statuses": True,
         "initial_regression": "15 failed, 355 passed; scoped empty classification and hospital detail controls",
         "iteration_1": "7 failed, 363 passed; empty UL was cropped out of seven fixture frames, corrected using exact original DOM",
         "iteration_2": "3 failed, 383 passed; proposed test retention 36500 exceeded Settings maximum 3650; review-2 results invalid for site conclusions",
         "iteration_3_full": "3 failed, 522 passed, 1 skipped; new test imported audit helper without restoring environment, fixed in test fixture",
         "resolution": "Production retention maximum unchanged; optional isolated identity replay bypasses expiry only inside its test context; environment restored after each B6 test",
         "followup_initial_guard": "Initial planned hosts omitted one EES saved-list sample; stopped before HTTP, then limited to exact saved anchors and same original column host",
         "final_tests": tests})
    save(OUT / "preservation.json", {"time": now, "changed_application_files": changed, "original_audit_files_unchanged": len(preparation["protected_hashes"]),
        "prior_reports_unchanged": len(preparation["prior_reports"]), "sources_yaml_sha256": sha(ROOT / "backend/config/sources.yaml"),
        "settings_yaml_unchanged": True, "frontend_unchanged": True, "production_db_connections": 0, "system_network_changes": 0,
        "formal_admissions": 0, "oa_requests": 0, "full_downloads": 0, "b7_executed": False})
    references = sum(group[v] for v in REFERENCES)
    hosts = len({urlsplit(t["url"]).hostname for t in targets})
    snapshot_times = sorted(r["time"] for r in captures.values() if r.get("time"))
    first, last = snapshot_times[0], snapshot_times[-1]
    report = ["# 吉林大学通知适配 B6 完整板块修复与验证报告", "",
        f"交付时间：{now}（Asia/Shanghai）。本批网络采集：{first} 至 {last}；离线复核时间另存于逐条记录。", "",
        "按用户“B6 和 B7 分两次，每次完成一整个大板块”的要求，本次覆盖原清单全部 **164 个 P2 入口**，并在 B6 交付点停止。B7 尚未执行。这里的完成指限定范围内的检查、可复现代码修复、逐条结论和独立候选交付，**不表示全部来源已支持或生产准入已完成**。", "",
        "## 1. 范围与结果", "",
        f"原口径：30 个曾失败、127 个部分通过、7 个抽样通过；按完整入口 URL 去重为 164 条，涉及 {hosts} 个主机。原始全校清单和报告保留原时间与原结论，不覆盖。", "",
        "其中 **163 个入口执行了本次访问检查，161 个取得页面、2 个访问受阻；1 个 OA 登录引用按用户要求未发请求**。5 个无需作为独立公开通知来源的性质结论与这些访问计数重叠，不能相加。", "",
        "| 本次结论 | 数量 | 含义 |", "| --- | ---: | --- |",
        f"| 有界内容／分页／隔离增量样本通过 | {group['BOUNDED_SAMPLE_PASSED_LIMITS_REMAIN']} | 本机保存页面核对通过；仍有下载、Cloud、历史等能力限制 |",
        f"| 当前空栏目 | {group['VERIFIED_EMPTY_COLUMN']} | 有明确零记录或空列表＋禁用分页证据；不能视为通知样本通过 |",
        f"| 权限受限 | {group['PERMISSION_RESTRICTED']} | 明确拒绝访问栏目；未证明登录能解决，未绕过 |",
        f"| 访问受阻 | {group['ACCESS_BLOCKED']} | 服务器断连或 robots 不可读取；不归为解析失败 |",
        f"| 能力／证据限制待处理 | {len(pending)} | 个别文章权限拒绝、外部图片、正文为空、发布日期未确认、重复发布候选 |",
        f"| 引用、静态介绍、目录或登录入口 | {references} | 不作为独立公开通知来源；OA 保持用户要求暂缓 |", "",
        f"完整环境准入 **0**；正式启用 **0**；新增独立候选 **{len(candidates)}**，全部禁用。无需作为栏目适配是目标性质结论，不表示该机构没有通知。", "",
        f"最终检查 {summary['list_pages']} 个列表页面记录、{summary['list_items']} 条去重后的各栏目列表记录（跨栏目不合并计数）、{summary['details']} 篇详情检查记录，其中 {summary['verified_details']} 篇通过标题／日期／正文／附件 DOM 对照。成功隔离两轮重放 {summary['isolated_replays']} 项；同文合并候选仍单列，不能据此推断生产数据库重复。", "",
        "[逐栏 CSV](jlu-b6-compatibility-report.csv) · [完整结果](jlu-fix-b6/review-accepted-20261015/results.json) · [最终统计](jlu-fix-b6/review-accepted-20261015/summary.json) · [候选](jlu-fix-b6/source-candidates.json) · [环境矩阵](jlu-fix-b6/admission-matrix.json)", "",
        "## 2. 实际修复", "",
        "1. **空栏目识别**：支持 VSB 空 UL 与全禁用首屏分页组合、旧版 `共0条 0/0` 分页表格及医院明确空数据容器；真实文章链接与空标记冲突时不宣告为空，不再退回导航。",
        "2. **医院 CMS**：五个有内容栏目复用高级选择器，标题和列表日期分开；详情使用 `.article_details1 .cont > .title`、`.liner`、`.cont > .text`；支持实际公开 GET 分页链接，不执行 JS 或猜接口。图片正文保留同源图链接，未下载图片或 OCR。",
        "3. **VSB 文章头部**：补经页面证明的作用域标题规则；未知 VSB h3/h5 仅在文章正文之前且有列表前缀／文档标题佐证时采用。新增未知头部日期回退仅使用文章正文之前的明确元信息；冲突或仅有更新／正文活动日期时保留未确认。",
        "4. **分类错抓和旧文漏抓**：同一带日期列表行中的分类链接不能借用文章日期。旧版 JSP 文章只识别 `urltype=news.NewsContentUrl` 且有单一合法 `wbtreeid/wbnewsid` 的已见链接，完整保留查询身份；树目录或异常参数不视为文章。两个实际旧文返回权限提示，已按明确权限受限分类，未伪装成成功详情。",
        "5. **相邻文章标题污染**：正文之后的上一条／下一条标题不覆盖当前通知。东北亚学院实际样本证明旧解析曾误用相邻链接文字。",
        "6. **明确 MP4 附件**：艺术学院附件区的合法视频下载链接现在保留名称、类型和完整参数；不把正文图片当附件，也不声称视频可自动下载。",
        "7. **奖学金误合并**：材料学院“学业奖学金”和“国家奖学金”通知具有不同正文和附件，原近似匹配在隔离库中只保留两条样本；修复后保留三条。仅拦截明确不同奖项的标题近似匹配，URL/public_id 优先级、14 天窗口、0.92 阈值、来源关系和用户状态保持。", "",
        "应用改动限于 `backend/app/parsers/html.py` 和 `backend/app/services/deduplication.py`。见 [本批代码差异](jlu-fix-b6/application-changes.diff)、[真实模板样本来源](../backend/tests/fixtures/jlu_b6/manifest.json)。", "",
        "## 3. 仍有限制的结果", "",
        "| 机构／栏目 | URL | 原因 |", "| --- | --- | --- |"]
    for p in pending:
        report.append(f"| {cell(p['institution'])}／{cell(p['column'])} | [{cell(p['url'])}]({p['url']}) | {cell(p['reason'])}；[记录](jlu-fix-b6/results/{p['id']}.json) |")
    report.extend(["", "- 商学招聘图片样本的外部／不允许图片引用未被放行，维持既有同源图片边界。",
        "- 软件学院空正文不以标题、导航或虚构文字填充。生物与农业工程学院静态就业介绍缺少可确认发布元信息，不用活动日或抓取日补齐。",
        "- 计算机学院两个同标题同日正文样本属于重复发布候选，但附件下载编号不同，未下载附件；保留人工复核，不据此在正式库合并或删除。",
        "- 药学院旧学院通知入口仍返回“您没有访问当前栏目的权限”；其官网公开通知和招生栏目分别核验，不能据此宣布旧受限入口恢复。",
        "- 法学院和东北亚学院两个旧版 JSP 详情返回 HTTP 200 并跳到权限提示页，明确写“您无权访问此页面”。已修复权限分类，保留文章受限结论；未猜测其他文章路径或尝试绕过。",
        "- 历史文化学院 `xwgg/tzgg.htm` 在本次请求断连；体育旧 `isc/oaindex.htm` 因 robots 断连停止。未关闭 TLS、改变网络出口或增加重试。",
        "- 数学招生入口嵌入单篇招生介绍、汽车招生入口是四个子板块的目录、医院停电链接是单篇文章、卓越工程师招生入口全部引用外站；分别排除为独立通知栏目，子板块与外站全文仍未纳入本批。",
        "- 原标签中附件端点、正文之外的历史样本和源数据编码问题未因样本通过而清零。CSV 保留原标签及本轮列表替换字符数；本批没有重新探测已知验证码／robots 限制的附件端点。", "",
        "食品学院教学信息列表本次仍有 **3 个替换字符**；详情抽样通过不代表列表其余源数据已修复，未盲目转码。此项与有界样本分类重叠，不另加进 164 条总数。", "",
        "## 4. 分页、重复和数据保护", "",
        "每栏目最多两页、每轮最多三篇合法文章详情（不足三篇全检）；修正错误采样后另补五篇详情，再为旧版 JSP 增补两篇模板控制，全部来自已保存列表的实际 href。初轮误选的分类入口保留请求证据，不能当作有效详情样本。没有请求第三页或开展历史补抓。", "",
        "隔离重放使用内存 SQLite，检查 notice 身份、来源关系、baseline、已读和收藏；旧于十年的样本仅在该身份测试上下文中关闭过期筛选，生产保留期最大值仍为 3650，默认策略未修改。此处是保存的解析样本重放，不能代替实际 Cloud/feed 或已安装客户端刷新。", "",
        f"本轮有界列表出现同 URL 跨栏目引用候选 {len(same_url)} 组、同标题同日期不同 URL 候选 {len(same_title)} 组。[候选台账](jlu-fix-b6/duplicate-candidates.json)保留来源与 URL；它们不是已证实的生产数据库重复。", "",
        "## 5. 执行环境、测试和证据", "",
        f"网络单进程串行，全局至少 1 秒、同源至少 1.2 秒，遵守更长 robots Crawl-delay；超时／瞬时 502/503/504 最多两次尝试，权限／403／429／证书／robots 限制停止。本批共 {network_attempts} 次 HTTP 请求尝试，最终缓存 {len(captures)} 个逻辑 URL 记录，核对 {html_checks} 个解码后 HTML 快照 SHA。", "",
        "无登录或验证码操作、无附件文件下载、无 OA 请求、无真实远程 Cloud/feed 请求、无正式数据库连接。Windows 公开抓取与离线重放分别记录；Cloud/Linux、公共 feed、安装客户端的当前状态仍未验证。", "",
        "| 验证 | 真实结果 |", "| --- | --- |",
        "| 本批前完整基线 | 487 passed, 1 skipped |",
        "| 首轮缺陷复现 | 15 failed, 355 passed |",
        "| 最终针对性回归 | 394 passed |",
        "| 最终完整后端回归 | 533 passed, 1 skipped |",
        "| 新增测试 | 46 项 |", "",
        "1 项跳过为未提供 `JLU_TEST_POSTGRES_URL` 的可选 PostgreSQL 集成测试；隔离入口不连接外部数据库，不能算作 PostgreSQL 或 Cloud 生产验收通过。", "",
        "[测试日志和指纹](jlu-fix-b6/final-manifest.json)与各阶段日志保留。中间的样本裁剪、测试保留期参数和审计 helper 导入环境泄漏均已修正；[工具迭代记录](jlu-fix-b6/tooling-iterations.json)说明其原因，不计为站点失败。未改 UI，因此未运行前端测试。", "",
        f"原审计 {len(preparation['protected_hashes'])} 个受保护文件、{len(preparation['prior_reports'])} 份先前批次报告 SHA 保持；正式 sources/settings、API、Cloud/Desktop 策略、数据库结构、前端和系统网络均未改。[保护校验](jlu-fix-b6/preservation.json)", "",
        "## 6. 原 30 个失败入口的逐条处置", "",
        "| 机构／栏目 | URL | 最新结论 | 证据 |", "| --- | --- | --- | --- |"])
    by_id = {m["id"]: m for m in matrix}
    for row in failures:
        m = by_id[row["id"]]
        report.append(f"| {cell(row['institution'])}／{cell(row['column'])} | [{cell(row['url'])}]({row['url']}) | {cell(m['status'])}／{cell(m['verdict'])} | [记录](jlu-fix-b6/results/{row['id']}.json) |")
    report.extend(["", "其余原 127 个部分通过、7 个抽样通过入口也全部纳入同一最终 CSV 和机器台账，未因原状态良好而跳过。", "",
        "## 7. 下一板块与未覆盖范围", "",
        "本次停在完整 B6。按用户安排，下一次执行整个 **B7：P3 研究机构／附属单位、失效入口与剩余发现缺口**；包括原 112 个 P3 入口口径、剩余三个 P3 空结果、P3 导航风险和访问限制，以及 44 个未发现栏目、305 条官网未知机构的有界补证。各口径有重叠，不相加当机构或故障数。", "",
        "B6 未覆盖：全部历史分页、非抽样详情、附件完整下载／校验和、图片 OCR、外站引用全文、需要访问权限的内容、实际 Cloud Linux/feed、客户端安装运行、正式数据库迁移。既有 OA 暂缓、招生日期未确认与本报告受限项继续保留，不因进入 B7 而改成已支持。", "",
        "本批未提交 GitHub、发布 Release、更新安装客户端或启用来源。后续正式准入应按指定环境逐条审查；B7 本次没有执行。", ""])
    report_path = ROOT / "docs/JLU_SITE_FIX_B6_REPORT.md"
    report_path.write_text("\n".join(report), encoding="utf-8")
    acceptance = {"time": now, "status": "B6_complete_scope_bounded_validation_delivered_limits_retained_B7_not_started",
        "entries": 164, "old_statuses": dict(Counter(t["old_status"] for t in targets)), "verdicts": dict(group),
        "old_failures_dispositions": dict(Counter(r["verdict"] for r in failures)), "candidate_configs": len(candidates), "all_candidates_disabled": True,
        "full_environment_admissions": 0, "tests": tests, "new_test_cases": 46, "details": summary["details"], "verified_details": summary["verified_details"],
        "list_pages": summary["list_pages"], "list_items": summary["list_items"], "isolated_replays": summary["isolated_replays"],
        "http_attempts": network_attempts, "access_checks": 163, "deferred_network_entries": 1, "first_screens_acquired": 161,
        "final_offline_http_attempts": 0, "fresh_followup_details": followup_details, "unique_capture_records": len(captures),
        "snapshot_hash_checks": html_checks, "original_audit_files_unchanged": len(preparation["protected_hashes"]), "prior_reports_unchanged": len(preparation["prior_reports"]),
        "production_db_connections": 0, "oa_requests": 0, "cloud_production_verified": False, "complete_downloads": 0, "frontend_changed": False, "b7_executed": False}
    files = changed + ["backend/scripts/verify_jlu_b1.py", "backend/scripts/audit_jlu_sites.py", "backend/scripts/validate_jlu_b5_c.py",
        "backend/scripts/prepare_jlu_b6.py", "backend/scripts/discover_jlu_b6.py", "backend/scripts/prepare_jlu_b6_fixtures.py",
        "backend/scripts/validate_jlu_b6.py", "backend/scripts/followup_jlu_b6.py", "backend/scripts/finalize_jlu_b6.py", "backend/tests/test_jlu_b6.py",
        "docs/JLU_SITE_FIX_B6_REPORT.md", "docs/jlu-b6-compatibility-report.csv", "docs/JLU_SITE_FIX_PLAN.md", "docs/JLU_FAILURE_REMEDIATION_PLAN.md"]
    acceptance["files"] = {p: sha(ROOT / p) for p in files}
    save(OUT / "acceptance.json", acceptance)
    print(json.dumps({k: v for k, v in acceptance.items() if k != "files"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
