from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import re

from db_movements.db import save_sputnik8_rows

BASE = "https://www.sputnik8.com/"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\xa0", " ").replace("\u202f", " ")
    return " ".join(text.split())


def parse_page():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options)

    all_events = []

    try:
        start_url = "https://www.sputnik8.com/ru/ekaterinburg?filters=priceFrom%3D0%26priceTo%3D3600"

        print("Открытие страницы...")
        driver.get(start_url)

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        print("Страница загружена.\n")

        time.sleep(3)

        load_more_attempts = 0
        max_attempts = 10
        while load_more_attempts < max_attempts:
            try:
                button = driver.find_element(By.CSS_SELECTOR,
                                             "button.button_oX-6.button_tag_button.button_fullwidth_wPfB.button_size_m_8e-p.button_color_secondary_kFnm.gtm_main-block_show-more")
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", button)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", button)
                load_more_attempts += 1
                time.sleep(2)

            except Exception as e:
                break

        print(
            f"\nВсего загружено карточек после нажатий: {len(driver.find_elements(By.CSS_SELECTOR, 'div.activity-card_n0wr'))}\n")

        soup = BeautifulSoup(driver.page_source, "html.parser")

        cards = soup.find_all("div", class_="activity-card_n0wr")

        for idx, card in enumerate(cards):
            try:
                title_elem = card.find('div', class_=lambda x: x and 'heading_' in x)
                title = clean_text(title_elem.get_text(strip=True)) if title_elem else "Не найдено"

                link_elem = card.find('a', role='link')
                if link_elem:
                    link_href = link_elem.get('href', '')
                    full_link = f"https://www.sputnik8.com{link_href}" if link_href else ""
                else:
                    full_link = ""

                rating = "Нет рейтинга"
                rating_elem = card.find('div', class_=lambda x: x and 'value-text_' in x)
                if rating_elem:
                    rating_text = rating_elem.get_text(strip=True)
                    rating_match = re.search(r'(\d+\.?\d*)', rating_text)
                    if rating_match:
                        rating = rating_match.group(1)

                reviews = "0"
                reviews_elem = card.find('div', class_=lambda x: x and 'rating-text_' in x)
                if reviews_elem:
                    reviews_text = reviews_elem.get_text(strip=True)
                    reviews_match = re.search(r'(\d+)', reviews_text)
                    if reviews_match:
                        reviews = reviews_match.group(1)

                price = "по запросу"
                price_elem = card.find('div', class_=lambda x: x and 'ui-amount_is-free' in x)
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    price_match = re.search(r'(\d[\d\s]*₽)', price_text)
                    if price_match:
                        price = clean_text(price_match.group(1))
                    else:
                        price = clean_text(price_text)

                tour_type = "Не указан"
                type_elem = card.find('div', class_=lambda x: x and 'detail_' in x)
                if type_elem:
                    type_text = type_elem.get_text(strip=True)
                    parts = type_text.split('•')
                    if parts:
                        tour_type = clean_text(parts[0])

                event_data = {
                    "title": title,
                    "link": full_link,
                    "rating": rating,
                    "reviews": reviews,
                    "price": price,
                    "type": tour_type,
                    "district": "все"
                }

                all_events.append(event_data)

            except Exception as e:
                continue

        if all_events:
            save_sputnik8_rows(all_events)

            print("=" * 60)
            print(f"✓ Найдено {len(all_events)} экскурсий")
        else:
            print("✗ Экскурсии не найдены")

    except Exception as e:
        print(f"ошибка: {e}")

    finally:
        driver.quit()
