"""Check or undo the authorized local Clash OA change from its exact backup.

Read-only by default. --apply removes this fix and reloads Clash. If the runtime
config has since changed, removes only the exact OA entries, preserving later edits.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import quote

import httpx
import yaml


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup-directory", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    home = (Path(os.environ["APPDATA"]) / "io.github.clash-verge-rev.clash-verge-rev").resolve()
    backup = args.backup_directory.resolve()
    if not backup.is_relative_to(home / "oa-egress-backups"):
        parser.error("Backup must be inside the local Clash OA backup directory")
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    if len(manifest["files"]) != 3:
        parser.error("Expected exactly the runtime config and two profile editor files")
    files = []
    preserve_later_changes = False
    proxy = {"name": "JLU-OA-Ethernet", "type": "direct",
             "interface-name": manifest["interface_name"], "ip-version": "ipv4"}
    rule = manifest["rule"]
    for item in manifest["files"]:
        path = Path(item["path"]).resolve()
        saved = (backup / item["backup"]).resolve()
        if (path != home / "clash-verge.yaml" and not path.is_relative_to(home / "profiles")) or not saved.is_relative_to(backup):
            parser.error("Manifest contains an unexpected target or backup path")
        original = saved.read_bytes()
        current = path.read_bytes()
        if hashlib.sha256(original).hexdigest() != item["before_sha256"]:
            parser.error("Backup checksum does not match")
        restored = original
        if hashlib.sha256(current).hexdigest() != item["after_sha256"]:
            preserve_later_changes = True
            data = yaml.safe_load(current)
            restored_data = copy.deepcopy(data)
            if path == home / "clash-verge.yaml":
                entries = data.get("proxies", [])
                if any(x.get("name") == proxy["name"] and x != proxy for x in entries):
                    parser.error("OA outbound was edited after the fix; refusing to remove it")
                if any(proxy["name"] in g.get("proxies", []) for g in data.get("proxy-groups", [])):
                    parser.error("OA outbound is referenced by a later proxy group; resolve that reference first")
                restored_data["proxies"] = [x for x in entries if x != proxy]
                restored_data["rules"] = [x for x in data.get("rules", []) if x != rule]
            elif "proxies" in data or any(isinstance(x, dict) for x in data.get("prepend", [])):
                entries = data.get("prepend", [])
                if any(isinstance(x, dict) and x.get("name") == proxy["name"] and x != proxy for x in entries):
                    parser.error("OA editor outbound was edited; refusing to remove it")
                restored_data["prepend"] = [x for x in entries if x != proxy]
            else:
                restored_data["prepend"] = [x for x in data.get("prepend", []) if x != rule]
            restored = yaml.safe_dump(restored_data, allow_unicode=True, sort_keys=False).encode("utf-8")
        files.append((path, restored, current))
    if not args.apply:
        print(json.dumps({"status": "ready", "files": len(files), "changes_made": False,
                          "preserve_later_changes": preserve_later_changes}))
        return
    runtime = yaml.safe_load(files[0][1])
    controller = "http://" + runtime["external-controller"]
    headers = {"Authorization": "Bearer " + str(runtime.get("secret", ""))}
    with httpx.Client(timeout=15, trust_env=False, headers=headers) as client:
        selectors = {name: x["now"] for name, x in client.get(controller + "/proxies").json()["proxies"].items()
                     if x.get("type") == "Selector" and x.get("now")}
        written = []
        try:
            for path, original, current in files:
                if path.read_bytes() != current:
                    raise RuntimeError("Configuration changed while preparing restore")
                path.write_bytes(original)
                written.append((path, original, current))
            client.put(controller + "/configs", params={"force": "true"}, json={"path": str(home / "clash-verge.yaml")}).raise_for_status()
        except BaseException:
            for path, original, current in written:
                if path.read_bytes() == original:
                    path.write_bytes(current)
            client.put(controller + "/configs", params={"force": "true"}, json={"path": str(home / "clash-verge.yaml")})
            raise
        now = client.get(controller + "/proxies").json()["proxies"]
        for name, selection in selectors.items():
            item = now.get(name, {})
            if item.get("now") != selection and selection in item.get("all", []):
                client.put(controller + "/proxies/" + quote(name, safe=""), json={"name": selection}).raise_for_status()
    print(json.dumps({"status": "restored", "files": len(files)}))


if __name__ == "__main__":
    main()
