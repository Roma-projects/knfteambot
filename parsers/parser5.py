import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from db_movements.db import save_kudaekb_free_rows
from discrictfinder.district_by_address import get_district_by_address

BASE = "https://kudaekb.ru"
START_URL = "https://kudaekb.ru/event/free/all/tomorrow/"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\xa0", " ").replace("\u202f", " ")
    return " ".join(text.split())


def parse_page(url: str):
    resp = requests.get(url, headers=HEADERS, allow_redirects=True)

    if resp.url != url:
        return None, True

    soup = BeautifulSoup(resp.text, "html.parser")

    lists = soup.find_all("div", class_="events_list")
    if not lists:
        return None, False

    events = []

    for lst in lists:
        for ev in lst.find_all("div", class_="event", itemtype="http://schema.org/Event"):
            start = ev.find("span", itemprop="startDate")
            end = ev.find("span", itemprop="endDate")
            place_addr = ev.find("span", itemprop="address")
            place_name = ev.find("span", itemprop="name")
            link_tag = ev.find("a", class_="eventname")

            start_txt = clean_text(start.get_text(strip=True)) if start else ""
            end_txt = clean_text(end.get_text(strip=True)) if end else ""
            title_txt = clean_text(link_tag.get_text(strip=True)) if link_tag else ""
            addr_txt = clean_text(place_addr.get_text(strip=True)) if place_addr else ""
            addr_extra_txt = clean_text(place_name.get_text(strip=True)) if place_name else ""
            url_full = urljoin(BASE, link_tag["href"]) if link_tag and link_tag.has_attr("href") else ""

            events.append(
                {
                    "source": "kudaekb_free",
                    "date": start_txt,
                    "time": "",
                    "start": start_txt,
                    "end": end_txt,
                    "title": title_txt,
                    "url": url_full,
                    "link": url_full,
                    "address": addr_txt,
                    "location": clean_text(" ".join(part for part in [addr_txt, addr_extra_txt] if part)),
                    "address_extra": addr_extra_txt,
                    "price": "Бесплатно",
                    "district": get_district_by_address(addr_txt),
                }
            )

    return events, False


def run():
    all_events = []

    events, stop = parse_page(START_URL)
    if events:
        all_events.extend(events)

    page = 2
    while True:
        url = f"{START_URL}{page}/"
        events, stop = parse_page(url)

        if stop:
            break
        if not events:
            break

        all_events.extend(events)
        page += 1

    save_kudaekb_free_rows(all_events)


if __name__ == "__main__":
    run()
