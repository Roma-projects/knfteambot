from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
from bs4 import BeautifulSoup
import time
import re
from discrictfinder.district_by_address import get_district_by_address
from db_movements.db import save_kovorkingi_online_rows

BASE = "https://kovorkingi.online"
START_URL = "https://kovorkingi.online/ru/ekb/"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def clean_text(text: str) -> str:
    if not text: return ""
    text = text.replace("\xa0", " ").replace("\u202f", " ")
    return " ".join(text.split())


def get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--log-level=3')
    options.add_argument('--silent')

    try:
        service = Service(ChromeDriverManager().install())
    except:
        service = Service(ChromeDriverManager(chrome_type=ChromeType.GOOGLE).install())

    return webdriver.Chrome(service=service, options=options)


def extract_schedule_from_text(text: str) -> str:
    if not text:
        return "не указан"

    text = re.sub(r'[\n\r\t]+', ' ', text.strip())
    text = re.sub(r'\s+', ' ', text)

    metro_pattern = r'Метро:\s*[^К]+?'
    match = re.search(metro_pattern + r'(?=Контакты|$)', text, re.IGNORECASE)

    if not match:

        match = re.search(r'Метро:\s*([^\n]+?)(?:\s*Контакты|$)', text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
        else:
            candidate = text
    else:
        candidate = match.group(0).replace('Метро:', '').strip()

    candidate = re.sub(r'^Екатеринбург[^,]*,?\s*', '', candidate, flags=re.IGNORECASE)
    candidate = candidate.strip()

    if not candidate or len(candidate) < 2:
        return "не указан"

    if re.match(r'^[\+\d\s\(\)-]{10,}', candidate):
        return "не указан"

    schedule_patterns = [
        r'\bкруглосуточно\b',
        r'ежедневно\s+с\s+\d{1,2}:\d{2}\s+до\s+\d{1,2}:\d{2}(?:,\s*(?:сб[-\s]*вс|выходные?|перерыв[^,]+))?[^К]*?(?=Контакты|$)',
        r'по\s+будням?\s+с\s+\d{1,2}:\d{2}\s+до\s+\d{1,2}:\d{2}(?:,\s*(?:сб[-\s]*вс|выходные?|перерыв[^,]+))?[^К]*?(?=Контакты|$)',
        r'в\s+будни?\s+с\s+\d{1,2}:\d{2}\s+до\s+\d{1,2}:\d{2}(?:,\s*(?:сб[-\s]*вс|выходные?))?[^К]*?(?=Контакты|$)',
        r'пн[-\s]*пт\s+с\s+\d{1,2}:\d{2}\s+до\s+\d{1,2}:\d{2}[^К]*?(?=Контакты|$)',
        r'(?:ежедневно|по будням|в будни|пн-пт|круглосуточно)?\s*с\s+\d{1,2}:\d{2}\s+до\s+\d{1,2}:\d{2}(?:,\s*[^К]+)?[^К]*?(?=Контакты|$)',
        r'\b(круглосуточно|ежедневно|по будням|в будни)\b',
    ]

    for pattern in schedule_patterns:
        match = re.search(pattern, candidate, re.IGNORECASE)
        if match:
            result = match.group(0).strip()

            result = re.sub(r'\s*Контакты.*$', '', result, flags=re.IGNORECASE).strip()

            if result and len(result) >= 3 and not result.startswith('+'):
                return result

    if any(kw in candidate.lower() for kw in ['с ', 'до ', ':', 'круглосуточно', 'будни', 'ежедневно', 'выходной']):

        candidate = re.split(r'\s*\+\d', candidate)[0].strip()
        if candidate and len(candidate) < 100:
            return candidate

    return "не указан"


def parse_coworking_cards(driver):
    wait = WebDriverWait(driver, 15)

    try:
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".card")))
        time.sleep(2)
    except:
        print("⚠ Карточки не загрузились")
        return []

    soup = BeautifulSoup(driver.page_source, "html.parser")
    cards = soup.select(".card")

    print(f"📋 Найдено карточек: {len(cards)}\n")

    results = []

    for idx, card in enumerate(cards, 1):
        try:
            data = {
                'name': '',
                'url': '',
                'address': '',
                'schedule': '',
                'district': '',
            }

            title_el = card.select_one("h3.title")
            if title_el:
                data['name'] = clean_text(title_el.get_text())

            data["url"] = START_URL

            addr_match = re.search(r'Адрес:\s*([^\nМ]+)', card.get_text())
            if addr_match:
                data_str = addr_match.group(1).strip()
                data['address'] = data_str
                data['district'] = get_district_by_address(data_str)
            data['schedule'] = extract_schedule_from_text(card.get_text())

            if data['name']:
                results.append(data)

        except Exception as e:
            print(f"⚠ Ошибка при парсинге карточки #{idx}: {e}")
            continue

    return results


def runkov():
    driver = get_driver()

    try:
        print(f"📄 Открытие: {START_URL}\n")
        driver.get(START_URL)

        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        print("✅ Страница загружена\n")
        time.sleep(3)

        all_coworkings = parse_coworking_cards(driver)

        if not all_coworkings:
            print("\n❌ Данные не найдены!")
            return
        save_kovorkingi_online_rows(all_coworkings)

        print(f"✓ Обработано коворкингов: {len(all_coworkings)}")


    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("\n🔄 Завершение работы...")
        time.sleep(2)
        driver.quit()


if __name__ == "__main__":
    runkov()
