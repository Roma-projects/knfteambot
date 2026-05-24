from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
from bs4 import BeautifulSoup
import time

from discrictfinder.district_by_address import get_district_by_address
from db_movements.db import save_gorpom_rows

BASE = "https://www.gorpom.ru"
START_URL = "https://www.gorpom.ru/list/kovorking/jekaterinburg/"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\xa0", " ").replace("\u202f", " ")
    return " ".join(text.split())


def get_driver(max_retries=3):
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

    for attempt in range(max_retries):
        try:
            driver_path = ChromeDriverManager().install()
            service = Service(executable_path=driver_path, log_path=None)

            driver = webdriver.Chrome(
                service=service,
                options=options,
            )

            driver.set_page_load_timeout(60)
            driver.implicitly_wait(10)
            return driver
        except Exception as e:
            print(f"⚠ Попытка {attempt + 1} создания драйвера не удалась: {e}")
            time.sleep(2)
    raise RuntimeError("Не удалось инициализировать ChromeDriver после нескольких попыток")


def click_show_more_buttons(driver):
    clicks_count = 0
    try:
        accept_btn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, "//button[text()='Да, верно']"))
        )
        accept_btn.click()
        time.sleep(1)
    except:
        print("ℹ️ Окно с локацией не появилось (или уже закрыто).")

    while True:
        try:
            show_more_btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".Pagination__nextPage"))
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", show_more_btn)
            time.sleep(0.5)
            show_more_btn.click()
            clicks_count += 1
            print(f"✅ Нажато раз: {clicks_count}")
            time.sleep(2)
        except:
            break
    return clicks_count


def parse_coworking_cards(driver):
    wait = WebDriverWait(driver, 15)
    try:
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".PlaceList__itemWrapper")))
        time.sleep(2)
    except:
        print("⚠ Карточки не загрузились")
        return []

    soup = BeautifulSoup(driver.page_source, "html.parser")
    cards = soup.select(".PlaceList__itemWrapper")
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

            name = card.select_one(".Place__headerLink")
            if name:
                data['name'] = clean_text(name.get_text())

            name_link = card.select_one("a.Place__wholeLink")
            if name_link:
                href = name_link.get('href', '')
                data['url'] = href if href.startswith('http') else BASE + href

            address_el = card.select_one(".Place__addressText")
            if address_el:
                data['address'] = clean_text(address_el.get_text())

            schedule_el = card.select_one(".Place__time")
            if schedule_el:
                data['schedule'] = clean_text(schedule_el.get_text())

            # Определение района по адресу
            address_clean = clean_text(address_el.get_text()) if address_el else ""
            data['district'] = get_district_by_address(address_clean) if address_clean else "все"

            if data['name']:
                results.append(data)
        except Exception as e:
            print(f"⚠ Ошибка при парсинге карточки #{idx}: {e}")
            continue
    return results


def run_go():
    driver = None
    try:
        driver = get_driver()
        driver.get(START_URL)
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(3)

        all_coworkings = parse_coworking_cards(driver)

        if not all_coworkings:
            print("\n❌ Данные не найдены!")
            return


        save_gorpom_rows(all_coworkings)

        print(f"✓ Обработано коворкингов: {len(all_coworkings)}")


    except Exception as e:
        print(f"\n ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n🔄 Завершение работы...")
        time.sleep(2)
        if driver:
            driver.quit()


if __name__ == "__main__":
    run_go()
