"""Re-apply category tags on the existing corpus without refetching sources."""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config import get_settings
from ingestion.stages.enrich import _CATEGORY_PATTERNS, _first_match


def main() -> int:
    path = Path(get_settings().scraped_json_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    before = Counter()
    after = Counter()
    for doc in payload.get("documents", []):
        before[doc.get("category") or "none"] += 1
        text = doc.get("text") or ""
        doc_category = _first_match(text, _CATEGORY_PATTERNS)
        if doc_category:
            doc["category"] = doc_category
        for chunk in doc.get("chunks") or []:
            chunk_text = chunk.get("text") or text
            tagged = _first_match(chunk_text, _CATEGORY_PATTERNS)
            if tagged:
                chunk["category"] = tagged
        after[doc.get("category") or "none"] += 1
    payload["exported_at"] = datetime.now(UTC).isoformat()
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print("before", dict(before))
    print("after", dict(after))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
