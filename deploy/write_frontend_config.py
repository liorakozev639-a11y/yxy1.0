"""Write the public frontend API configuration during static-site builds."""

from __future__ import annotations

import os
from pathlib import Path


def js_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def main() -> None:
    api_base_url = os.environ.get("FREE_TIME_API_BASE_URL", "").strip()
    output = Path(
        os.environ.get(
            "FRONTEND_CONFIG_OUTPUT",
            Path(__file__).resolve().parents[1] / "frontend" / "config.js",
        )
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "\n".join(
            [
                "(function (root) {",
                "  if (!root) return;",
                f"  root.FREE_TIME_API_BASE_URL = '{js_string(api_base_url)}';",
                "}(typeof window !== 'undefined' ? window : null));",
                "",
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

