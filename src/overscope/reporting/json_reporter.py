from __future__ import annotations

import json

from overscope.models import OverscopeReport


def render_json(report: OverscopeReport) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True, ensure_ascii=False)
