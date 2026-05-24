from html import escape

BTN_SEARCH = "🔍 Найти досуг"
BTN_ABOUT = "ℹ️ О боте"
BTN_HELP = "❓ Помощь"

UNKNOWN_USE_MENU = "Используй кнопки меню 👇"

START_TITLE = "<b>👋 Привет!</b>\n\n"
START_BODY = (
    "Я помогу найти интересный досуг в твоём городе.\n"
    "Нажми кнопку ниже, чтобы начать 👇"
)

MAIN_MENU_TEXT = "<b>Добро пожаловать в главное меню</b>"

MAX_RESULT_BYTES = 3500


def start_greeting() -> str:
    return START_TITLE + START_BODY


def city_in_development_alert(city_name: str) -> str:
    return f"🚧 {city_name} пока в разработке"


def step_pick_city() -> str:
    return "🌆 <b>Шаг 1 из 3</b> — Выбери город:"


def step_pick_area(city_name: str) -> str:
    return (
        f"🌆 Город: <b>{city_name}</b>\n\n"
        "🏙 <b>Шаг 2 из 3</b> — Выбери район:"
    )


def step_pick_date(city_name: str, area_name: str) -> str:
    return (
        f"🌆 Город: <b>{city_name}</b>\n"
        f"🏙 Район: <b>{area_name}</b>\n\n"
        "📅 <b>Шаг 3 из 3</b> — Выбери дату:"
    )


ABOUT_TEXT = (
    "<b>ℹ️ О боте</b>\n\n"
    "Помогаю найти мероприятия и досуг в городах Урала.\n\n"
    "<b>Поддерживаемые города:</b>\n"
    "✅ Екатеринбург\n"
    "🚧 Челябинск <i>(скоро)</i>\n"
    "🚧 Магнитогорск <i>(скоро)</i>\n"
    "🚧 Тюмень <i>(скоро)</i>"
)

HELP_TEXT = (
    "<b>❓ Помощь</b>\n\n"
    "• Нажми <b>🔍 Найти досуг</b> и следуй шагам\n"
    "• Выбери город → район → дату\n"
    "• Получи список мероприятий\n\n"
    "<b>Команды:</b>\n"
    "/start — перезапустить бота\n"
)

DATE_MANUAL_PROMPT = (
    "✏️ Введи дату в формате <code>ДД.ММ.ГГГГ</code>\n"
    "Например: <code>25.12.2026</code>"
)

DATE_INVALID = (
    "❌ Неверный формат!\n"
    "Введи дату как <code>01.01.2026</code>"
)

SECTION_TITLES = {
    "main": "🎉 <b>Найдено мероприятий:</b>",
    "coworking": "💼 <b>Найдено коворкингов:</b>",
    "tours": "🚌 <b>Найдено экскурсий:</b>",
}

EMPTY_SECTION_TEXTS = {
    "main": "😔 <b>Мероприятий пока нет.</b>\nПопробуй другую дату или район.",
    "coworking": "😔 <b>Коворкинги по выбранному городу и району не найдены.</b>",
    "tours": "😔 <b>Экскурсии по выбранным параметрам не найдены.</b>",
}


def _message_size(text: str) -> int:
    return len(text.encode("utf-8"))


def _format_value(value) -> str:
    if value is None:
        return ""

    if hasattr(value, "strftime"):
        return value.strftime("%d.%m.%Y")

    return str(value)


def _clip(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value

    return value[: limit - 3].rstrip() + "..."


def _format_header(*,
                   total: int,
                   city: str,
                   area: str,
                   date_str: str,
                   section: str,
                   page: int | None = None,
                   total_pages: int | None = None,
                   ) -> str:
    header = [
        f"{SECTION_TITLES.get(section, SECTION_TITLES['main'])} {total}",
        "",
    ]

    if city not in (None, "Не выбран"):
        header.append(f"🌆 Город: <b>{escape(str(city))}</b>")

    if area not in (None, "Любой район"):
        header.append(f"🏙 Район: <b>{escape(str(area))}</b>")

    if section != "coworking" and date_str not in (None, "Любая дата"):
        header.append(f"📅 Дата: <b>{escape(str(date_str))}</b>")

    if page is not None and total_pages and total_pages > 1:
        header.append(f"Страница {page + 1} из {total_pages}")

    return "\n".join(header)


def _format_event_block(index: int, event: dict, section: str) -> str:
    title = escape(_clip(str(event.get("title") or "Без названия"), 250))
    block = [f"<b>{index}. {title}</b>"]

    date_range_start = _format_value(event.get("date_range_start"))
    date_range_end = _format_value(event.get("date_range_end"))

    if date_range_start or date_range_end:
        if date_range_start and date_range_end and date_range_start != date_range_end:
            block.append(
                f"📅 Период: {escape(date_range_start)} — {escape(date_range_end)}"
            )
        else:
            block.append(f"📅 Дата: {escape(date_range_start or date_range_end)}")
    elif section != "coworking":
        event_date = _format_value(event.get("event_date"))

        if event_date:
            block.append(f"📅 Дата: {escape(event_date)}")

    if section != "coworking":
        start_time = escape(str(event.get("start_time") or ""))
        end_time = escape(str(event.get("end_time") or ""))

        if start_time and end_time:
            block.append(f"🕒 Время: {start_time} - {end_time}")
        elif start_time:
            block.append(f"🕒 Время: {start_time}")

    address = escape(_clip(str(event.get("address") or ""), 700))

    if address:
        block.append(f"📍 Адрес: {address}")

    price = escape(_clip(str(event.get("price") or ""), 250))

    if section != "coworking" and price:
        block.append(f"💰 Цена: {price}")

    schedule = escape(_clip(str(event.get("schedule") or ""), 350))

    if section == "coworking" and schedule:
        block.append(f"📆 График: {schedule}")

    link = str(event.get("link") or "").strip()

    if link.startswith(("http://", "https://")):
        block.append(f'🔗 <a href="{escape(link, quote=True)}">Подробнее</a>')

    return "\n".join(block)


def _build_result_pages(*,
                        events: list[dict],
                        city: str,
                        area: str,
                        date_str: str,
                        section: str,
                        ) -> list[list[str]]:
    base_header = _format_header(
        total=len(events),
        city=city,
        area=area,
        date_str=date_str,
        section=section,
    )

    pages: list[list[str]] = []
    current_blocks: list[str] = []

    for index, event in enumerate(events, start=1):
        block = _format_event_block(index, event, section)
        candidate = "\n\n".join([base_header] + current_blocks + [block])

        if current_blocks and _message_size(candidate) > MAX_RESULT_BYTES:
            pages.append(current_blocks)
            current_blocks = [block]
        else:
            current_blocks.append(block)

    if current_blocks:
        pages.append(current_blocks)

    return pages or [[]]


def search_results(city: str,
                   area: str,
                   date_str: str,
                   section: str = "main",
                   ) -> str:
    header = _format_header(
        total=0,
        city=city,
        area=area,
        date_str=date_str,
        section=section,
    )

    body = EMPTY_SECTION_TEXTS.get(section, EMPTY_SECTION_TEXTS["main"])

    return f"{header}\n\n{body}"


def format_results_page(*,
                        events: list[dict],
                        city: str,
                        area: str,
                        date_str: str,
                        section: str = "main",
                        page: int = 0,
                        ) -> tuple[str, int, int]:
    if not events:
        return search_results(city, area, date_str, section), 0, 1

    pages = _build_result_pages(
        events=events,
        city=city,
        area=area,
        date_str=date_str,
        section=section,
    )
    total_pages = len(pages)
    page = max(0, min(page, total_pages - 1))

    header = _format_header(
        total=len(events),
        city=city,
        area=area,
        date_str=date_str,
        section=section,
        page=page,
        total_pages=total_pages,
    )
    text = "\n\n".join([header] + pages[page])

    return text, page, total_pages


def format_events_result(events, city: str, area: str, date_str: str) -> str:
    text, _, _ = format_results_page(
        events=list(events),
        city=city,
        area=area,
        date_str=date_str,
        section="main",
        page=0,
    )
    return text


NEW_SEARCH_HEADER = step_pick_city

KB_BACK = "◀️ Назад"
KB_CANCEL_INLINE = "❌ Отмена"
KB_NEW_SEARCH = "🔄 Новый поиск"
KB_CHANGE_DATE = "📅 Изменить дату"
KB_MANUAL_DATE = "✏️ Ввести дату вручную"
