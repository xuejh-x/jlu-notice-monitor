from __future__ import annotations

from typing import Any

from app.sources.base import NoticeSource
from app.sources.ccst import CcstSource
from app.sources.cse import CseSource
from app.sources.csw import CswSource
from app.sources.innovation import InnovationSource
from app.sources.jwc import JwcSource
from app.sources.oa import OASource

SOURCE_TYPES: dict[str, type[NoticeSource]] = {
    "ccst": CcstSource,
    "cse": CseSource,
    "csw": CswSource,
    "innovation": InnovationSource,
    "jwc": JwcSource,
    "oa": OASource,
}


def build_source(config: dict[str, Any]) -> NoticeSource:
    parser_name = str(config.get("parser", config["code"]))
    source_type = SOURCE_TYPES.get(parser_name)
    if source_type is None:
        raise ValueError(f"Unknown source parser: {parser_name}")
    return source_type(config)
