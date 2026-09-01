"""Write web/public/dashboard-bootstrap.json from the live JSON dashboard."""

from __future__ import annotations

import json
from pathlib import Path

from api.json_dashboard import get_dashboard_bootstrap

ROOT = Path(__file__).resolve().parents[1]
DESTS = (
    ROOT / "web" / "public" / "dashboard-bootstrap.json",
    ROOT / "web" / "src" / "data" / "dashboard-bootstrap.json",
)


def main() -> None:
    payload = get_dashboard_bootstrap()
    text = json.dumps(payload, ensure_ascii=False)
    for dest in DESTS:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
        print(f"Wrote {dest} ({dest.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
