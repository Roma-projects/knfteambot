from playwright.sync_api import sync_playwright
from db_movements.db import save_mayakovsky_park_rows

DETAILS_URL = "https://xn--e1agfrc5b.xn--p1ai/afisha"


def parse_calendar():
    url = "https://calendar.google.com/calendar/u/0/embed?mode=AGENDA&src=c21tLnBhcmsubWF5YWtvdnNrb2dvQGdtYWlsLmNvbQ"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="ru-RU")
        page = context.new_page()

        page.goto(url, timeout=60000)

        page.wait_for_selector('div[role="button"]', timeout=60000)

        for _ in range(5):
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(1000)

        elements = page.query_selector_all('div[role="button"]')

        events = []
        seen = set()

        for el in elements:
            aria = el.get_attribute("aria-label")

            if not aria:
                continue

            parts = [p.strip() for p in aria.split(",")]

            time_text = parts[0] if len(parts) > 0 else ""
            title = parts[1] if len(parts) > 1 else ""

            location = ""
            for p_part in parts:
                if "Место проведения:" in p_part:
                    location = p_part.replace("Место проведения:", "").strip()

            date = parts[-1] if len(parts) > 0 else ""

            key = (title, date)
            if key in seen:
                continue
            seen.add(key)

            events.append({
                "source": "mayakovsky_park_calendar",
                "title": title,
                "date": date,
                "time": time_text,
                "location": "Парк Маяковского:" + location,
                "price": "",
                "details": DETAILS_URL,
                "district": "Октябрьский",
            })

        browser.close()

        if events:
            save_mayakovsky_park_rows(events)
            print(f"✓ Найдено событий: {len(events)}")
        else:
            print("✗ События не найдены")
