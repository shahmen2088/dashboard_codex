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
    parser.add_argument("--expected-projects", type=int, default=10)
    parser.add_argument("--query", default="Bitrix24")
    parser.add_argument("--expected-query-results", type=int, default=4)
    parser.add_argument("--description-query", default="")
    parser.add_argument("--expected-description-results", type=int, default=0)
    parser.add_argument("--project", default="Presentation video")
    args = parser.parse_args()
    errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url, wait_until="networkidle")

        assert page.title() == "Карта истории Codex"
        assert page.locator(".hero .eyebrow").inner_text().casefold() == "органайзер истории codex"
        assert int(page.locator("#stat-sessions").inner_text()) > 0
        assert page.locator(".project-card").count() == args.expected_projects
        assert page.locator("#chat-list .chat-row").count() > 0
        assert page.locator(".chat-row__locator").count() > 0
        assert page.locator("#refresh-interval").input_value() == "60"
        assert "Источник обновлён" in page.locator("#freshness").inner_text()
        assert page.locator("#setup-steps .setup-step").count() == 4
        assert page.locator("#setup-summary").inner_text() == "Готово к работе"
        assert page.locator("#view-tech").is_hidden()
        assert page.locator('[data-view="tech"]').count() == 1
        assert page.locator("#filters").evaluate("(el) => Boolean(el.compareDocumentPosition(document.querySelector('#project-grid')) & Node.DOCUMENT_POSITION_FOLLOWING)")

        page.locator("#query").fill(args.query)
        page.wait_for_timeout(150)
        assert page.locator("#chat-list .chat-row").count() == args.expected_query_results

        if args.description_query:
            page.locator("#query").fill(args.description_query)
            page.wait_for_timeout(150)
            assert page.locator("#chat-list .chat-row").count() == args.expected_description_results

        page.locator(f'[data-project="{args.project}"]').click()
        page.wait_for_selector(".detail-panel__description", state="visible")
        detail_text = page.locator("#detail-panel").inner_text()
        assert args.project in detail_text, detail_text
        assert page.locator(".detail-panel__description").count() == 1
        assert page.locator(".detail-panel__description").is_visible()
        assert "описание проекта" in detail_text.casefold()

        page.locator('[data-view="table"]').click()
        assert page.locator("#view-table").is_visible()
        assert page.locator(".history-table tbody tr").count() > 0

        page.locator('[data-view="board"]').click()
        assert page.locator("#view-board").is_visible()
        assert page.locator(".board-column").count() == 3
        assert "уровень: высокий" in page.locator("#view-board").inner_text()

        page.locator('[data-view="timeline"]').click()
        assert page.locator("#view-timeline").is_visible()
        assert page.locator(".timeline-item").count() > 0

        page.locator('[data-view="graph"]').click()
        assert page.locator("#view-graph").is_visible()
        assert page.locator(".graph-node").count() == args.expected_projects
        assert "История" in page.locator("#history-graph").text_content()

        page.locator('[data-view="tech"]').click()
        assert page.locator("#view-tech").is_visible()
        assert page.locator("#view-tech .technical-card").is_visible()
        assert page.locator("#setup-panel").is_visible()
        assert page.locator("#view-tech #freshness").is_visible()
        page.screenshot(path=args.screenshot, full_page=True)

        mobile = browser.new_page(viewport={"width": 390, "height": 850})
        mobile.goto(args.url, wait_until="networkidle")
        assert mobile.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1")
        mobile.locator('[data-view="tech"]').click()
        assert mobile.locator("#view-tech").is_visible()
        mobile.close()
        browser.close()

    if errors:
        print("console_errors:")
        print("\n".join(errors))
        return 1
    print(f"browser verification passed; screenshot={Path(args.screenshot).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
