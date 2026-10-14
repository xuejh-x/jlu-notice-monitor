from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

import httpx
import pytest
import yaml

from scripts import restore_oa_egress


def prepare_backup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    home = tmp_path / "io.github.clash-verge-rev.clash-verge-rev"
    backup = home / "oa-egress-backups/test"
    backup.mkdir(parents=True)
    (home / "profiles").mkdir()
    proxy = {"name": "JLU-OA-Ethernet", "type": "direct", "interface-name": "Ethernet", "ip-version": "ipv4"}
    rule = "DOMAIN,oa.jlu.edu.cn,JLU-OA-Ethernet"
    original = [
        {"external-controller": "127.0.0.1:9097", "secret": "fixture-secret",
         "proxies": [{"name": "Original", "type": "direct"}], "rules": ["MATCH,DIRECT"],
         "proxy-groups": [{"name": "Group", "type": "select", "proxies": ["Original"]}]},
        {"prepend": [], "append": [], "delete": []},
        {"prepend": [], "append": [], "delete": []},
    ]
    after = copy.deepcopy(original)
    after[0]["proxies"].insert(0, proxy)
    after[0]["rules"].insert(0, rule)
    after[1]["prepend"].append(proxy)
    after[2]["prepend"].append(rule)
    current = copy.deepcopy(after)
    current[0]["proxies"].append({"name": "Later", "type": "direct"})
    current[0]["rules"].insert(1, "DOMAIN,later.test,Later")
    current[0]["dns"] = {"enable": True}
    current[0]["proxy-groups"][0]["proxies"].append("Later")
    current[1]["prepend"].append({"name": "Later", "type": "direct"})
    current[2]["prepend"].append("DOMAIN,later.test,Later")
    paths = [home / "clash-verge.yaml", home / "profiles/proxies.yaml", home / "profiles/rules.yaml"]
    files = []
    for index, path in enumerate(paths):
        saved = yaml.safe_dump(original[index]).encode()
        (backup / f"{index}.original").write_bytes(saved)
        path.write_text(yaml.safe_dump(current[index]), encoding="utf-8")
        files.append({"path": str(path), "backup": f"{index}.original",
                      "before_sha256": hashlib.sha256(saved).hexdigest(),
                      "after_sha256": hashlib.sha256(yaml.safe_dump(after[index]).encode()).hexdigest()})
    (backup / "manifest.json").write_text(json.dumps({"interface_name": "Ethernet", "rule": rule, "files": files}), encoding="utf-8")
    return backup, paths, current


def test_restore_dry_run_and_apply_preserve_later_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    backup, paths, current = prepare_backup(tmp_path, monkeypatch)
    args = ["restore", "--backup-directory", str(backup)]
    monkeypatch.setattr(sys, "argv", args)
    restore_oa_egress.main()
    assert [yaml.safe_load(p.read_bytes()) for p in paths] == current
    requests = []

    def respond(request: httpx.Request):
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"proxies": {}})
        return httpx.Response(204)

    real_client = httpx.Client
    monkeypatch.setattr(restore_oa_egress.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(respond), **kw))
    monkeypatch.setattr(sys, "argv", [*args, "--apply"])
    restore_oa_egress.main()
    restored = [yaml.safe_load(p.read_bytes()) for p in paths]
    assert [x["name"] for x in restored[0]["proxies"]] == ["Original", "Later"]
    assert restored[0]["rules"] == ["DOMAIN,later.test,Later", "MATCH,DIRECT"]
    assert restored[0]["dns"] == current[0]["dns"]
    assert restored[0]["proxy-groups"] == current[0]["proxy-groups"]
    assert restored[1]["prepend"] == [{"name": "Later", "type": "direct"}]
    assert restored[2]["prepend"] == ["DOMAIN,later.test,Later"]
    assert sum(r.method == "PUT" for r in requests) == 1


@pytest.mark.parametrize("later_edit", ["changed_outbound", "group_reference"])
def test_restore_refuses_conflicting_later_use_without_writes(
    later_edit: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    backup, paths, current = prepare_backup(tmp_path, monkeypatch)
    if later_edit == "changed_outbound":
        current[0]["proxies"][0]["interface-name"] = "Other"
    else:
        current[0]["proxy-groups"][0]["proxies"].append("JLU-OA-Ethernet")
    paths[0].write_text(yaml.safe_dump(current[0]), encoding="utf-8")
    before = [p.read_bytes() for p in paths]
    monkeypatch.setattr(sys, "argv", ["restore", "--backup-directory", str(backup), "--apply"])
    with pytest.raises(SystemExit, match="2"):
        restore_oa_egress.main()
    assert [p.read_bytes() for p in paths] == before
