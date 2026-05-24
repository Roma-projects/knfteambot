from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
from db_movements.db import save_yeltsin_center_rows
from discrictfinder.district_by_address import get_district_by_address


def parse_yeltsin_center_free_events():
    MONTHS = [
        'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
        'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'
    ]

    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        print("Открытие страницы...")
        driver.get("https://yeltsin.ru/affairs/")

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        print("Страница загружена.\n")

        time.sleep(3)

        for i in range(5):
            try:
                button = driver.find_element(By.CSS_SELECTOR, "div.ShowMoreButton_showMoreContainer_2NcQh button")
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", button)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", button)
                print(f"Попытка {i + 1}/5: Кнопка нажата")
                time.sleep(2)
            except:
                print("Кнопка не найдена")
                break

        time.sleep(2)

        events = driver.find_elements(By.XPATH, "//a[contains(@href, '/affair/')]")
        print(f"\nВсего найдено событий: {len(events)}\n")

        free_events = []

        for idx, event in enumerate(events):
            try:
                event_text = event.text

                if "Вход свободный" in event_text or "Бесплатно" in event_text:
                    title = ""
                    try:
                        h3_elem = event.find_element(By.TAG_NAME, "h3")
                        title = h3_elem.text.strip()
                    except:
                        pass

                    price_text = ""
                    if "Вход свободный" in event_text:
                        price_text = "Вход свободный"
                    elif "Бесплатно" in event_text:
                        price_text = "Бесплатно, по регистрации" if "по регистрации" in event_text else "Бесплатно"

                    lines = [line.strip() for line in event_text.split('\n') if line.strip()]

                    date = ""
                    time_text = ""
                    location = ""

                    for line in lines:
                        has_month = any(month in line.lower() for month in MONTHS)

                        if ("до" in line.lower() or has_month) and len(line) < 30:
                            date = line
                        elif ("–" in line or "-" in line) and ":" in line and len(line) < 20:
                            time_text = line
                        elif (len(line) < 50 and date not in line and time_text not in line and
                              "Вход свободный" not in line and "Бесплатно" not in line and
                              "по регистрации" not in line):
                            if not location and len(line) > 3:
                                location = line

                    href = event.get_attribute("href")
                    link = href if href else ""
                    district = get_district_by_address(location)

                    if title:
                        free_events.append({
                            "id": len(free_events),
                            "source": "yeltsin_center",
                            "title": title,
                            "date": date,
                            "time": time_text,
                            "location": location,
                            "price": price_text,
                            "link": link,
                            "district": district
                        })
            except:
                continue

        if free_events:
            save_yeltsin_center_rows(free_events)
            print(f"✓ Найдено {len(free_events)} бесплатных событий")
        else:
            print("✗ Бесплатные события не найдены")

    except Exception as e:
        print(f"Критическая ошибка: {e}")
    finally:
        driver.quit()
