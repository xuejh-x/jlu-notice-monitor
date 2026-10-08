from __future__ import annotations

from collections import Counter
from datetime import datetime
from hashlib import sha256
import json
from typing import Any

from app.schemas.notice import NoticeCandidate
from app.sources.base import SourceError
from app.sources.lqb import SECTION_LABELS


def baseline_key(source_id: int) -> str:
    return f"single-page-baseline:{source_id}"


def prepare_snapshot(
    snapshot: dict[str, Any], previous_value: str | None, *, source_identity: str,
    url: str, now: datetime, bootstrap: bool = False,
) -> tuple[str, NoticeCandidate | None]:
    previous = None
    if previous_value is not None:
        try:
            previous = json.loads(previous_value)
            if (previous["version"] != 1 or not isinstance(previous["revision"], int)
                    or previous["revision"] < 0 or not isinstance(previous["edition"], int)
                    or not isinstance(previous["first_detected_at"], str)
                    or set(previous["sections"]) != set(SECTION_LABELS)
                    or any(not isinstance(lines, list) or not lines
                           or any(not isinstance(line, str) for line in lines)
                           for lines in previous["sections"].values())):
                raise ValueError("invalid baseline")
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise SourceError("LQB_BASELINE_INVALID: existing baseline retained") from exc
    sections = snapshot["sections"]
    hashes = {key: sha256("\n".join(lines).encode("utf-8")).hexdigest()
              for key, lines in sections.items()}
    changed = [key for key in SECTION_LABELS if previous is not None
               and previous["sections"][key] != sections[key]]
    edition_changed = previous is not None and previous["edition"] != snapshot["edition"]
    revision = previous["revision"] if previous else 0
    candidate = None
    if previous and (changed or edition_changed):
        revision += 1
        if not bootstrap:
            chunks = ["本通知记录页面重要内容的变化；首次检测时间不是官方发布时间。"]
            if edition_changed:
                chunks.append(f"赛事届次：第{previous['edition']}届 → 第{snapshot['edition']}届")
            for key in changed:
                old, new = Counter(previous["sections"][key]), Counter(sections[key])
                removed, added = list((old - new).elements()), list((new - old).elements())
                detail = [f"【{SECTION_LABELS[key]}】"]
                if removed:
                    detail.append("变更前：\n" + "\n".join(removed))
                if added:
                    detail.append("变更后：\n" + "\n".join(added))
                if not removed and not added:
                    detail.extend(["原顺序：\n" + "\n".join(previous["sections"][key]),
                                   "现顺序：\n" + "\n".join(sections[key])])
                chunks.append("\n".join(detail))
            fingerprint = sha256(json.dumps(
                [source_identity, revision, snapshot["edition"], hashes],
                sort_keys=True, ensure_ascii=False,
            ).encode("utf-8")).hexdigest()
            # Revisions use strict identities; original URL remains untouched.
            candidate = NoticeCandidate(
                public_id=f"lqb:{fingerprint}", origin_item_key=f"snapshot:{fingerprint}",
                title=f"第{snapshot['edition']}届蓝桥杯信息更新：" +
                      "、".join(SECTION_LABELS[key] for key in changed or ["subjects", "schedule"]),
                url=url, publisher="蓝桥杯赛事信息（吉林大学）", content="\n\n".join(chunks),
            )
    value = json.dumps({"version": 1, "edition": snapshot["edition"], "sections": sections,
                        "hashes": hashes, "revision": revision,
                        "first_detected_at": previous["first_detected_at"] if previous else now.isoformat(),
                        "last_checked_at": now.isoformat()}, ensure_ascii=False, sort_keys=True)
    return value, candidate
