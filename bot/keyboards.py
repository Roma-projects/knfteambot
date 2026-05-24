from datetime import datetime, timedelta

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


class CityCallback(CallbackData, prefix="city"):
    code: str


class AreaCallback(CallbackData, prefix="area"):
    code: str


class DateCallback(CallbackData, prefix="date"):
    value: str


class NavCallback(CallbackData, prefix="nav"):
    to: str


class MenuCallback(CallbackData, prefix="menu"):
    action: str


class ResultCallback(CallbackData, prefix="result"):
    section: str
    page: int = 0


CITY_NAMES = {
    "ekb": "Екатеринбург",
    "chlb": "Челябинск",
    "mgn": "Магнитогорск",
    "tmn": "Тюмень",
}

AREA_NAMES = {
    "akadem_ekb": "Академический",
    "vis_ekb": "Верх-Исетский",
    "zhd_ekb": "Железнодорожный",
    "kir_ekb": "Кировский",
    "len_ekb": "Ленинский",
    "oct_ekb": "Октябрьский",
    "oed_ekb": "Орджоникидзевский",
    "chk_ekb": "Чкаловский",
}

today = datetime.now()


def get_sunday(td: datetime) -> str:
    days_ahead = 6 - td.weekday()
    if days_ahead < 0:
        days_ahead += 7
    return (td + timedelta(days=days_ahead)).strftime("%Y.%m.%d")


def get_saturday(td: datetime) -> str:
    days_ahead = 5 - td.weekday()
    if days_ahead < 0:
        days_ahead += 7
    return (td + timedelta(days=days_ahead)).strftime("%Y.%m.%d")


DATE_PRESETS = {
    today.strftime("%Y.%m.%d"): "Сегодня",
    (today + timedelta(days=1)).strftime("%Y.%m.%d"): "Завтра",
    get_saturday(today): "Суббота",
    get_sunday(today): "Воскресенье",
    "manual": "Ввести вручную",
}


def back_to_main_butt() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="⬅ Назад",
            callback_data=NavCallback(to="back_to_menu").pack(),
        )
    )
    return builder.as_markup()


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="🔍 Найти досуг",
            callback_data=MenuCallback(action="search").pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="❓ Помощь",
            callback_data=MenuCallback(action="help").pack(),
        ),
        InlineKeyboardButton(
            text="ℹ️ О боте",
            callback_data=MenuCallback(action="about").pack(),
        ),
    )

    return builder.as_markup()


def cities_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for city_code, city_name in CITY_NAMES.items():
        builder.row(
            InlineKeyboardButton(
                text=city_name,
                callback_data=CityCallback(code=city_code).pack(),
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="⬅ Назад",
            callback_data=NavCallback(to="back_to_menu").pack(),
        )
    )

    return builder.as_markup()


def areas_keyboard(city_code: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if city_code == "ekb":
        for area_code, area_name in AREA_NAMES.items():
            builder.row(
                InlineKeyboardButton(
                    text=area_name,
                    callback_data=AreaCallback(code=area_code).pack(),
                )
            )

    builder.row(
        InlineKeyboardButton(
            text="⏭ Пропустить",
            callback_data=NavCallback(to="skip_area").pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="⬅ Назад",
            callback_data=NavCallback(to="back_to_city").pack(),
        )
    )

    return builder.as_markup()


def date_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for value, text in DATE_PRESETS.items():
        builder.row(
            InlineKeyboardButton(
                text=text,
                callback_data=DateCallback(value=value).pack(),
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="⏭ Пропустить",
            callback_data=NavCallback(to="skip_date").pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="⬅ Назад",
            callback_data=NavCallback(to="back_to_area").pack(),
        )
    )

    return builder.as_markup()


def manual_date_back_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="⬅ Назад к выбору даты",
            callback_data=NavCallback(to="back_to_date").pack(),
        )
    )
    return builder.as_markup()


def results_keyboard(
        *,
        section: str = "main",
        page: int = 0,
        total_pages: int = 1,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    navigation_buttons = []

    if page > 0:
        navigation_buttons.append(
            InlineKeyboardButton(
                text="⬅ Назад",
                callback_data=ResultCallback(
                    section=section,
                    page=page - 1,
                ).pack(),
            )
        )

    if page + 1 < total_pages:
        navigation_buttons.append(
            InlineKeyboardButton(
                text="Далее ➡",
                callback_data=ResultCallback(
                    section=section,
                    page=page + 1,
                ).pack(),
            )
        )

    if navigation_buttons:
        builder.row(*navigation_buttons)

    if section == "main":
        builder.row(
            InlineKeyboardButton(
                text="💼 Найти коворкинги",
                callback_data=ResultCallback(
                    section="coworking",
                    page=0,
                ).pack(),
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="🚌 Найти экскурсии",
                callback_data=ResultCallback(
                    section="tours",
                    page=0,
                ).pack(),
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="🔍 Начать новый поиск",
            callback_data=NavCallback(to="new_search").pack(),
        )
    )

    return builder.as_markup()
