from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import time
import re
from datetime import datetime, date, timedelta
from db_movements.db import save_yandex_afisha_rows
from discrictfinder.district_by_address import get_district_by_address

DAYS_OF_WEEK = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']

MONTHS = {
    'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5, 'июня': 6,
    'июля': 7, 'августа': 8, 'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12,
    'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'июн': 6, 'июл': 7, 'авг': 8,
    'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12
}


def clean_price(price):
    if not price:
        return ""
    price = re.sub(r'^от\s*', '', price.strip(), flags=re.IGNORECASE)
    return price.strip()


def parse_datetime_location(raw_text):
    if not raw_text:
        return None, None, ""

    text = raw_text.strip()
    event_date = None
    start_time = None

    if re.search(r'\bсегодня\b', text, flags=re.IGNORECASE):
        event_date = date.today()
        text = re.sub(r'\bсегодня\b\s*,?\s*', '', text, flags=re.IGNORECASE)
    elif re.search(r'\bзавтра\b', text, flags=re.IGNORECASE):
        event_date = date.today() + timedelta(days=1)
        text = re.sub(r'\bзавтра\b\s*,?\s*', '', text, flags=re.IGNORECASE)

    for day in DAYS_OF_WEEK:
        text = re.sub(rf'\b{day}\b,?\s*', '', text, flags=re.IGNORECASE)

    text = re.sub(r'^до\s*,?\s*', '', text, flags=re.IGNORECASE)

    if re.search(r'постоянная экспозиция', text, flags=re.IGNORECASE):
        if event_date is None:
            event_date = date.today()
        text = re.sub(r'постоянная экспозиция\s*,?\s*', '', text, flags=re.IGNORECASE)

    date_pattern = r'(\d{1,2})\s+([а-яё]+)(?:\s+(\d{4}))?'
    date_matches = list(re.finditer(date_pattern, text.lower()))
    found_dates = []
    current_year = datetime.now().year

    for match in date_matches:
        try:
            day = int(match.group(1))
            month_name = match.group(2)
            year = int(match.group(3)) if match.group(3) else current_year
            month = MONTHS.get(month_name)
            if month:
                try:
                    parsed_date = date(year, month, day)
                    found_dates.append(parsed_date)
                except ValueError:
                    pass
        except Exception:
            continue

    if len(found_dates) > 1:
        if event_date is None:
            today = date.today()
            event_date = min(found_dates, key=lambda d: abs((d - today).days))
    elif len(found_dates) == 1 and event_date is None:
        event_date = found_dates[0]

    time_match = re.search(r'(\d{1,2}:\d{2})', text)
    if time_match:
        start_time = time_match.group(1)

    address = text
    address = re.sub(date_pattern, '', address, flags=re.IGNORECASE)
    address = re.sub(r'\d{1,2}:\d{2}', '', address)

    address = re.sub(r'\s*,\s*', ', ', address)
    address = re.sub(r'\s+', ' ', address)
    address = address.strip(', ')

    return event_date, start_time, address


def parse_yandex_afisha(date=None, period='13'):
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')

    url = f"https://afisha.yandex.ru/yekaterinburg?date={date}&multiFilter=4.pushkin-card&period={period}"

    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        print(f"Открытие: {url}")
        print(f"Дата: {date}, Период: {period} дней\n")

        driver.get(url)
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(3)

        print("Загрузка всех событий...")
        click_count = 0

        while True:
            time.sleep(1)
            try:
                show_more_button = driver.find_element(By.CSS_SELECTOR, 'button[data-test-id="eventsList.more"]')
                if show_more_button.is_displayed():
                    driver.execute_script("arguments[0].scrollIntoView(true);", show_more_button)
                    time.sleep(0.5)
                    driver.execute_script("arguments[0].click();", show_more_button)
                    time.sleep(2)
                    click_count += 1
                else:
                    break
            except NoSuchElementException:
                break

        event_cards = driver.find_elements(By.CSS_SELECTOR, 'div[data-test-id="eventCard.root"]')

        events = []
        seen_links = set()

        for card in event_cards:
            try:
                try:
                    link_elem = card.find_element(By.CSS_SELECTOR, 'a[data-test-id="eventCard.link"]')
                    link = link_elem.get_attribute('href')
                except Exception:
                    link = ""

                if link in seen_links:
                    continue
                seen_links.add(link)

                try:
                    title_elem = card.find_element(By.CSS_SELECTOR, 'h2[data-test-id="eventCard.eventInfoTitle"]')
                    title = title_elem.text.strip()
                except Exception:
                    title = ""

                try:
                    price_elems = card.find_elements(By.CSS_SELECTOR, 'span[data-test-id="eventCard.price"]')
                    prices = [clean_price(elem.text.strip()) for elem in price_elems]
                    price = ", ".join(filter(None, prices))
                except Exception:
                    price = ""

                date_time_raw = ""
                try:
                    details_list = card.find_element(By.CSS_SELECTOR, 'ul[data-test-id="eventCard.eventInfoDetails"]')
                    li_elems = details_list.find_elements(By.TAG_NAME, 'li')
                    date_time_parts = [li.text.strip() for li in li_elems if li.text.strip()]
                    date_time_raw = ", ".join(date_time_parts)
                except Exception:
                    pass

                event_date, start_time, address = parse_datetime_location(date_time_raw)

                if title:
                    events.append({
                        'id': len(events),
                        'title': title,
                        'event_date': event_date,
                        'start_time': start_time,
                        'end_time': None,
                        'address': address,
                        'price': price or "Бесплатно",
                        'link': link,
                        'district': get_district_by_address(address),
                        'city': 'Екатеринбург'
                    })

            except Exception as e:
                print(f"Ошибка при парсинге карточки: {e}")
                continue

        if events:
            save_yandex_afisha_rows(events)
            print(f"✓ Найдено {len(events)} уникальных событий")
        else:
            print("\n✗ События не найдены")

    except Exception as e:
        print(f"Критическая ошибка парсера: {e}")
        import traceback
        traceback.print_exc()
    finally:
        driver.quit()


if __name__ == "__main__":
    parse_yandex_afisha()
