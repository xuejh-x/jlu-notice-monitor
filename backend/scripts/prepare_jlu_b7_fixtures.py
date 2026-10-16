"""Derive small real DOM fixtures from captured B7 pages, retaining provenance."""
import hashlib
import json
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "docs/jlu-fix-b7/live-20261015"
OUT = ROOT / "backend/tests/fixtures/jlu_b7"
CONTROLS = [
    ("dwxcb", "https://dwxcb.jlu.edu.cn/info/1046/2926.htm", "form[name='_newscontent_fromname']", "中共吉林大学第十五届委员会第五轮巡视完成进驻", "2026-05-12"),
    ("ddy", "https://ddy.jlu.edu.cn/info/1009/1613.htm", "form[name='_newscontent_fromname']", "关于开展地质调查项目合同（协议）成交额自查工作的通知", "2026-09-07"),
    ("oic", "https://oic.jlu.edu.cn/info/1623/10107.htm", ".right-nr", "吉林大学与俄罗斯托姆斯克理工大学合作举办物理学专业本科教育项目2024年度办学报告", "2026-01-19"),
    ("jgb", "https://jgb.jlu.edu.cn/info/1003/1722.htm", "form[name='_newscontent_fromname']", "关于确定周永东同志为2020年党员计划发展对象的公示", "2019-12-12"),
    ("zcyfg", "https://zcyfg.jlu.edu.cn/info/1048/1675.htm", "form[name='_newscontent_fromname']", "政策与法规办公室召开2026年工作务虚会", "2026-03-06"),
    ("iamp", "http://iamp.jlu.edu.cn/info/1029/10063.htm", "form[name='_newscontent_fromname']", "吉林大学原子与分子物理研究所2027年推免生拟录取名单公示", "2026-10-13"),
    ("wordpress", "https://synlab.jlu.edu.cn/2025/09/5172.html", "article.type-post", "2025年申请重点实验室开放课题基金的通知", "2025-09-08"),
    ("fszx", "https://fszx.jlu.edu.cn/info/1018/3696.htm", "form[name='_newscontent_fromname']", "吉林大学附属中学2026年报刊订阅项目实行单一来源采购方式的公示", "2025-11-19"),
    ("gjs", "http://gjs.jlu.edu.cn/info/1046/1833.htm", "table:has(> tr > td.content > #vsb_content)", "2018年度高等教育研究所招收硕士研究生拟录取汇总", "2018-04-02"),
    ("pftheory", "http://pftheory.jlu.edu.cn/info/1015/3926.htm", "form[name='_newscontent_fromname']", "第二届高清海学术基金评奖公告", None),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cache = json.loads((INPUT / "requests.json").read_text(encoding="utf-8"))
    previous = {c["file"]: c for c in json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))} if (OUT / "manifest.json").exists() else {}
    manifest = []
    for name, url, selector, title, date in CONTROLS:
        source = INPUT
        if url not in cache:
            source = ROOT / "docs/jlu-fix-b7/followup-1-20261015"
        r = cache.get(url) or json.loads((source / "requests.json").read_text(encoding="utf-8"))[url]
        raw = (source / r["html_path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == r["sha256"]
        soup = BeautifulSoup(raw.decode("utf-8"), "html.parser")
        frame = soup.select_one(selector)
        assert frame is not None and title in frame.get_text()
        # Retain real metadata/body/attachment DOM; omit unrelated navigation and trackers.
        html = "<title>" + soup.title.get_text() + "</title>" + str(frame)
        dest = OUT / (name + ".html")
        if dest.exists():
            prior = previous[dest.name]
            assert prior["source_sha256"] == r["sha256"] and prior["fixture_sha256"] == hashlib.sha256(dest.read_bytes()).hexdigest(), "Preserve existing fixtures"
        else:
            dest.write_text(html, encoding="utf-8")
        manifest.append({"name": name, "file": dest.name, "url": url, "title": title, "date": date,
            "selector": selector, "captured_at": r["time"], "source_snapshot": source.relative_to(ROOT).as_posix() + "/" + r["html_path"],
            "source_sha256": r["sha256"], "fixture_sha256": hashlib.sha256(dest.read_bytes()).hexdigest()})
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = json.loads((INPUT / "results.json").read_text(encoding="utf-8"))
    samples = [{"id": r["id"], "url": r["url"], "samples": [d["parsed"] for d in r["details"]],
                "evidence": [{"url": d["url"], "sha256": d["response"]["sha256"]} for d in r["details"]]}
               for r in rows if r["url"] in {"http://nlshm-lab.jlu.edu.cn/yjsjy/zsxx.htm", "http://iamp.jlu.edu.cn/rcpy/zsxx.htm"}]
    (OUT / "admission-identity.json").write_text(json.dumps(samples, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Real fixtures:", len(manifest))


if __name__ == "__main__":
    main()
