"""Write web/public/dashboard-bootstrap.json from the live JSON dashboard."""

from __future__ import annotations

import json
from pathlib import Path

from api.json_dashboard import get_dashboard_bootstrap

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "web" / "public" / "dashboard-bootstrap.json"


def main() -> None:
    payload = get_dashboard_bootstrap()
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {DEST} ({DEST.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
