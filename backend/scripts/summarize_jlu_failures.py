"""Summarize recorded audit failures without network or application/DB imports."""
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
INPUTS = [
    ("原始审计", "docs/jlu-audit-evidence/results.json"),
    ("B1 实时", "docs/jlu-fix-b0-b1/live-existing-20261013/results.json"),
    ("B2 实时", "docs/jlu-fix-b2/live-20261014/results.json"),
    ("B3 实时", "docs/jlu-fix-b3/live-existing-20261014/results.json"),
    ("B4 实时初判", "docs/jlu-fix-b4/live-20261014/results.json"),
    ("B4 最终离线复核", "docs/jlu-fix-b4/review-final-20261014/results.json"),
]
HASHES = {}


def read(name):
    raw = (ROOT / name).read_bytes()
    HASHES[name] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw.decode("utf-8-sig"))


def cell(value):
    return str(value or "—").replace("|", "／").replace("\n", " ").replace("\r", " ")


def link(path, label):
    return f"[{label}]({Path(path).relative_to('docs').as_posix()})"


def main():
    time = datetime.now(timezone(timedelta(hours=8))).isoformat()
    history = defaultdict(list)
    stages = {}
    for stage, name in INPUTS:
        stages[stage] = read(name)
        for r in stages[stage]:
            url = r.get("column_url") or r["url"]
            history[url].append({"stage": stage, "url": url, "status": r["status"],
                "time": r.get("checked_at") or r.get("captured_at"), "reviewed_at": r.get("validated_at"),
                "reason": r.get("reason", ""), "issues": r.get("issues", []), "verdict": r.get("verdict"),
                "evidence": r.get("evidence_file") or name, "input": name,
                "institution": r.get("institution"), "column": r.get("column"), "priority": r.get("priority")})
    failures = {url: events for url, events in history.items() if any(e["status"] in {"失败", "需认证"} for e in events)}
    original = [r for r in stages["原始审计"] if r["status"] == "失败"]
    assert len(original) == 48
    original_map = {r["column_url"]: r for r in original}
    ledger = []
    for url, events in failures.items():
        old = original_map.get(url, {})
        latest = events[-1]
        if "POSSIBLE_NAVIGATION_CAPTURE" in old.get("issues", []):
            disposition = "导航误抓已拦截；来源尚未准入"
            explanation = "B1/B2/B4 历史快照控制不再产生导航候选；可能是真空栏目、旧路径或未知模板，不能标为已支持。"
        elif latest["status"] == "部分通过":
            if latest["verdict"] and "DATE_SEMANTICS" in latest["verdict"]:
                disposition = "内容结构已核对；发布日期含义待确认"
                explanation = "原站仅显示更新时间，不能独立确认发布日期；附件与分页/环境限制仍保留。"
            else:
                disposition = "已有修复或复核证据；仍为部分通过"
                explanation = "列表/正文样本已改善，尚未完成附件全量、历史分页及真实 Cloud 准入。"
        elif latest["status"] == "需认证":
            disposition = "明确栏目权限限制"
            explanation = "教务 1402 返回 HTTP 200 的无权限提示；未证实登录可解决，不绕过访问控制。"
        elif "EMPTY_LIST" in old.get("issues", []):
            disposition = "原空结果；未获后续逐栏复验"
            explanation = "仅证实当时未解析出通知；可能是真空、模板/动态接口、目标类型或权限问题，原因待确认。"
        else:
            disposition = "访问或链接受阻"
            explanation = latest["reason"]
        ledger.append({"url": url, "institution": events[0]["institution"], "column": events[0]["column"],
            "priority": old.get("priority") or events[0].get("priority") or "P1",
            "first_failed_stage": next(e["stage"] for e in events if e["status"] in {"失败", "需认证"}),
            "latest_record": latest, "disposition": disposition, "explanation": explanation, "events": events})
    ledger.sort(key=lambda r: (r["priority"], r["disposition"], r["url"]))
    counts = Counter(r["disposition"] for r in ledger)
    assert len(ledger) == 60 and counts["导航误抓已拦截；来源尚未准入"] == 27
    assert counts["原空结果；未获后续逐栏复验"] == 11
    assert counts["访问或链接受阻"] == 7
    assert counts["明确栏目权限限制"] == 1
    assert counts["内容结构已核对；发布日期含义待确认"] == 6
    assert counts["已有修复或复核证据；仍为部分通过"] == 8
    sites = [s for s in read("docs/jlu-audit-evidence/discovery.json") if s["status"] == "unreachable"]
    assert len(sites) == 15
    site_counts = Counter()
    for s in sites:
        reason = s["reason"]
        category = ("robots 明确禁止" if "ROBOTS_DISALLOWED" in reason else
                    "证书有效期校验失败" if "TLS_CERTIFICATE_VERIFY_FAILED" in reason else
                    "HTTP 403 访问限制" if "HTTP_403" in reason else
                    "服务器断开响应" if "Server disconnected" in reason else "robots 不可取得；原异常细节不足")
        s["summary_category"] = category
        site_counts[category] += 1
    attachment_history = defaultdict(list)
    for p in read("docs/jlu-fix-b3/attachment-matrix.json"):
        attachment_history[p["url"]].append({"stage": "B3", "probe": p})
    for r in stages["B4 最终离线复核"]:
        for p in r["attachment_probes"]:
            attachment_history[p["url"]].append({"stage": "B4 原实时探测，离线引用", "probe": p})
    attachment_counts = Counter(v[-1]["probe"]["category"] for v in attachment_history.values())
    event_counts = Counter(e["status"] for row in ledger for e in row["events"] if e["status"] in {"失败", "需认证"})
    save = {"generated_at": time, "scope": "原始审计最终清单+B1/B2/B3实时+B4实时初判及最终离线复核；不重复累计中间重放/别名",
        "network_requests": 0, "database_imported": False, "unique_failed_or_permission_columns": len(ledger),
        "failure_event_counts": dict(event_counts), "disposition_counts": dict(counts), "columns": ledger,
        "discovery_blocked_sites": sites, "discovery_categories": dict(site_counts),
        "attachment_unique_endpoint_counts": dict(attachment_counts), "attachment_endpoint_history": dict(attachment_history),
        "input_sha256": HASHES}
    (DOCS / "jlu-failure-summary.json").write_text(json.dumps(save, ensure_ascii=False, indent=2), encoding="utf-8")
    text = ["# 吉林大学通知适配历次失败汇总", "", f"整理时间：{time}（Asia/Shanghai）。只汇总已保存证据，本次不联网、不运行 crawler、不访问正式数据库、不修改来源。",
        "", "## 1. 先看结论", "",
        "原始审计最终清单有 **48 个失败栏目**：27 个疑似导航误抓、14 个空列表、7 个访问或链接受阻。它们并非 48 个站点，也不是 48 个当前仍坏的解析器。",
        "",
        "合并原审计、B1/B2/B3 实时结果、B4 首轮初判及最终离线复核，按完整栏目 URL 去重得到 **60 个曾失败或权限受限的栏目**，对应 70 条失败事件和 1 条权限事件。这个数含已修复问题及工具初判，不能称为当前失败总数。更早审计初判、别名及中间重放不重复累计，原始记录保持不变。",
        "", "| 最新有证据的处置状态 | 栏目数 | 含义 |", "| --- | ---: | --- |",
        "| 导航误抓已拦截 | 27 | 已阻止伪通知；栏目是否为空/旧路径/需专门选择器仍逐条待准入 |",
        "| 已有修复或复核，仍部分通过 | 8 | 就业两个栏目、CSE 学院通知、科研处、人文社科处、研究生院、团委、国际教育 |",
        "| 内容结构已核对，发布日期待确认 | 6 | 招生栏目只显示更新时间，不可当作已核验发布日期 |",
        "| 原空结果，尚未后续逐栏复验 | 11 | 不知道是空栏目、模板不支持、动态加载、目标类型或权限问题 |",
        "| 访问/链接受阻 | 7 | OA、答辩入口、两个继续教育入口、体育的两个索引/登录入口、数量经济旧链接 |",
        "| 明确栏目权限限制 | 1 | 教务教学公示 1402；未证实登录能解决 |",
        "",
        "7 个访问/链接项中，OA、答辩和两个继续教育入口共 4 个有 B3/B4 的较新受阻证据；体育两个入口和数量经济旧链接仅有原审计证据，当前状态未知。不能将它们全部宣称今天仍失败。",
        "", "## 2. 原因分类", "",
        "| 原因 | 具体表现 | 现有处理与剩余工作 |", "| --- | --- | --- |",
        "| 列表回退过宽 | 真空栏目、旧路径或未知模板被扫描成导航通知；原 27 项中 10 项还出现正文导航污染 | B1 收紧文章识别并拒绝导航；27 个快照候选从 1,178 降到 0。风险已拦截，不等于 27 栏目已支持 |",
        "| 模板未适配 | 就业 details?id 链接不符合旧静态文章规则，标题/日期/正文容器不同 | B4 复用高级选择器，修复两个就业栏目；其他模板不能凭 HTTP 200 或非空判断适配 |",
        "| 真实空/不支持尚难区分 | 其余 11 个原空列表缺少逐条新证据 | P2/P3 复核原页、栏目目标和动态机制；禁止导航回退补结果 |",
        "| 正文形式和附件范围不足 | CSE 图片正文被当成不支持；软件教办六个 jpg 未提取 | B2 保留同源原图 URL，B3 提取明确附件；没有 OCR、自动图像下载或历史库补写 |",
        "| 元信息提取错误 | 标题截断、正文小标题覆盖标题、把摘要公示期当发布日期 | B2/B4 按实际文章容器修复；招生更新日期的含义仍未确认 |",
        "| 网络/TLS | OA 在 robots 阶段 TLS EOF；答辩入口 robots 连接超时 | 未取得正文时停止，不改 TLS 或绕访问规则；OA 曾在 B1 成功、B2/B3 又受阻，说明可达性有时间/路径变化，不能只归因解析器 |",
        "| 重定向和失效入口 | 继续教育两个入口 HTTP 308 超过既有跳转上限；数量经济旧入口 404 | 核对官方新入口或站点侧跳转；没有证明循环根因，不提高上限伪造通过 |",
        "| 权限/访问规则 | 教务无权限页、图书馆 robots 禁止、招生办 robots 403、附件验证码 | 保留合法入口并停止；认证/验证码/规则问题不是加选择器能解决的 |",
        "| 证书有效期 | 附属高中 jdgz 原证据为证书有效期校验失败 | 站点/时钟/链路需核实，不能把 OA EOF 和证书有效期混为一类 |",
        "| 验证器初判局限 | 图片 URL 加入纯文本后对照失败，部分标题容器未纳入对照，权限页被算空列表 | B4 使用同一 SHA 快照修正复核，保留初判；最终 15 部分通过、1 权限、3 受阻，不把离线时间当实时抓取时间 |",
        "", "## 3. 附件、分页与其他未闭环项", "",
        "原审计 **108 个栏目**带附件端点问题标签，仅说明未确认取得文件，不是 108 个附件损坏；不能把后续少量验证码样本外推到全部。B3 11 个端点为 9 验证码页、2 文件前缀；B4 14 个为 8 验证码页、5 文件前缀、1 robots 阻止。按实际附件完整 URL 去重及取最新有限记录的数量如下：", ""]
    text.extend(f"- {category}：{count} 个端点。" for category, count in sorted(attachment_counts.items()))
    text += ["", "所有探测均未验证完整下载。HTML 验证码页可能返回 HTTP 206，所以 HTTP 状态成功不能当文件成功。原始各批次次数与去重端点数分别保留在 JSON，不相加当损坏数量。",
        "", "原审计另有分页未配置 189 个栏目、列表日期缺失 77 个、编码替换字符 1 个，以及同 URL 113 组、同标题/日期 48 组重复候选。这些是可重叠问题/待验收范围，不计入 48 个失败的主因分类，也没有证据证明全部日常漏抓或数据库重复。食品学院替换字符已存在于响应原字节，不能靠盲目转码修好。B5 验证分页、增量和去重；本轮不执行 B5。",
        "", "## 4. 60 个曾失败/权限栏目的完整台账", "",
        "下表保留最近一次已有记录的时间，不表示重新检查。导航拦截项列中的旧失败状态没有被覆盖，处置栏另说明修复范围。逐次事件的原始原因、标签、时间、证据及输入 SHA 见 [机器台账](jlu-failure-summary.json)。",
        "", "| # | 优先级／机构／栏目 | 栏目 URL | 处置状态 | 最近记录及时间 | 证据 |", "| --- | --- | --- | --- | --- | --- |"]
    for index, row in enumerate(ledger, 1):
        e = row["latest_record"]
        text.append(f"| {index} | {cell(row['priority'])}／{cell(row['institution'])}／{cell(row['column'])} | [{cell(row['url'])}]({row['url']}) | {cell(row['disposition'])} | {cell(e['stage'])}：{cell(e['status'])}；{cell(e['time'])}" + (f"；复核 {cell(e['reviewed_at'])}" if e.get("reviewed_at") else "") + f" | {link(e['evidence'], '记录')} |")
    text += ["", "## 5. 站点发现阶段另有 15 个受阻入口", "",
        "这是站点入口口径，与上面的栏目台账有重叠，不能相加。以下均为 2026-10-13 原始发现记录，未逐站重新访问。多数旧异常丢失细节，不能擅自认定为 DNS、超时或证书问题。",
        "", "| 机构 | 入口 | 当时原因分类 | 时间 |", "| --- | --- | --- | --- |"]
    for s in sites:
        text.append(f"| {cell('、'.join(s['institutions']))} | [{s['site_url']}]({s['site_url']}) | {s['summary_category']} | {s['checked_at']} |")
    text += ["", "证据：[完整发现记录](jlu-audit-evidence/discovery.json)。另有 44 个入口未发现栏目、305 条机构官网未知，它们是覆盖发现缺口，不是已证实抓取失败或无需适配。",
        "", "## 6. 建议处理顺序", "",
        "1. P0：OA 的默认访问/TLS 与实际 Cloud 路径先分别定位；既有来源持续回归。保留 B1 成功与 B2/B3 失败的不同时间证据。",
        "2. P1：先验收已修复的就业、学工、科研等内容的分页/增量，再确认六个招生日期语义。教学公示、答辩和继续教育分别按权限、网络和跳转问题处理。",
        "3. P2：27 个导航风险虽然已拦截，仍须逐条确认真空/旧路径/新模板；先复核学院和医院空列表。不要重新放开导航回退。",
        "4. P3：处理其他空列表、失效官方链接和站点发现缺口；robots/验证码限制保留，不绕过。",
        "",
        "早期回归日志也出现过环境变量导致的 4 个默认设置断言失败及同期代码变化中的 6 个 HTTP 诊断测试失败，后续完整回归已通过。它们不计为网站失败；B4 最终结果为 365 passed、1 skipped，跳过的 PostgreSQL 集成环境未配置不能算 Cloud 生产验收。",
        "", "## 7. 依据与限制", "",
        "依据：[原审计](JLU_SITE_AUDIT.md)、[B0＋B1](JLU_SITE_FIX_B0_B1_REPORT.md)、[B2](JLU_SITE_FIX_B2_REPORT.md)、[B3](JLU_SITE_FIX_B3_REPORT.md)、[B4](JLU_SITE_FIX_B4_REPORT.md)。原审计初步清单在 [initial-validation-results](jlu-audit-evidence/initial-validation-results.json)，未与最终去重清单重复累计。本汇总没有重写旧结论或声称未复验的来源已恢复。",
        "",
        "本汇总仅按这些批次已保存的栏目 URL 建立台账，不是全校当前故障率、当前失败总数、Cloud 健康检查或数据库修复任务。所有候选正式准入状态仍按原报告，未新增支持。", ""]
    report = DOCS / "JLU_FAILURE_SUMMARY.md"
    report.write_text("\n".join(text), encoding="utf-8")
    assert event_counts == {"失败": 70, "需认证": 1}
    for row in ledger:
        assert (ROOT / row["latest_record"]["evidence"]).exists()
    for name, sha in HASHES.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha
    print(json.dumps({"report": str(report), "columns": len(ledger), "dispositions": dict(counts),
                      "blocked_discovery_sites": len(sites), "unique_attachment_endpoints": len(attachment_history),
                      "attachment_categories": dict(attachment_counts), "network_requests": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
