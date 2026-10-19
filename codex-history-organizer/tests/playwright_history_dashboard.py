from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8787/")
    parser.add_argument("--screenshot", default=os.path.join(os.getenv("TEMP", "."), "codex-history-dashboard.png"))
    args = parser.parse_args()
    errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url, wait_until="networkidle")

        assert page.title() == "Карта истории Codex"
        assert page.locator("#stat-sessions").inner_text() == "47"
        assert page.locator(".project-card").count() == 10
        assert page.locator("#session-list .session-row").count() > 0

        page.locator("#query").fill("Bitrix24")
        page.wait_for_timeout(150)
        assert page.locator("#session-list .session-row").count() == 4

        page.locator('[data-project="Presentation video"]').click()
        page.wait_for_selector("#detail-panel h3", state="visible")
        detail_text = page.locator("#detail-panel").inner_text()
        assert "Presentation video" in detail_text, detail_text
        page.screenshot(path=args.screenshot, full_page=True)
        browser.close()

    if errors:
        print("console_errors:")
        print("\n".join(errors))
        return 1
    print(f"browser verification passed; screenshot={Path(args.screenshot).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
