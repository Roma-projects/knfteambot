from __future__ import annotations
import re
from datetime import date, datetime, timedelta
from typing import Iterable, List, Optional
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from db_movements import PARSER_TABLES, connect_parser_db

MAIN_EVENT_DATABASES = {
    "kudaekb_free": {
        "table": PARSER_TABLES["kudaekb_free"],
    },
    "mayakovsky_park": {
        "table": PARSER_TABLES["mayakovsky_park"],
    },
    "yandex_afisha": {
        "table": PARSER_TABLES["yandex_afisha"],
    },
    "yeltsin_center": {
        "table": PARSER_TABLES["yeltsin_center"],
    },
}

COWORKING_DATABASES = {
    "gorpom": {
        "table": PARSER_TABLES["gorpom"],
    },
    "kovorkingi_online": {
        "table": PARSER_TABLES["kovorkingi_online"],
    },
}

TOUR_DATABASES = {
    "sputnik8": {
        "table": PARSER_TABLES["sputnik8"],
    },
}

SKIP_VALUES = {
    None,
    "",
    "Любой район",
    "Любая дата",
    "Не выбран",
    "Пропустить",
}

RU_MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}


def _is_selected(value) -> bool:
    return value not in SKIP_VALUES


def normalize_date(date_value) -> Optional[date]:
    if isinstance(date_value, datetime):
        return date_value.date()

    if isinstance(date_value, date):
        return date_value

    if not date_value or date_value in SKIP_VALUES:
        return None

    text = str(date_value).strip()

    for fmt in (
            "%d.%m.%Y",
            "%Y.%m.%d",
            "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    return _parse_date_value(text)


def _parse_date_value(value) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if not value:
        return None

    text = str(value).strip().lower()

    if not text:
        return None

    today = date.today()

    if "сегодня" in text:
        return today

    if "завтра" in text:
        return today + timedelta(days=1)

    iso_match = re.search(r"\d{4}-\d{2}-\d{2}", text)

    if iso_match:
        try:
            return datetime.strptime(iso_match.group(0), "%Y-%m-%d").date()
        except ValueError:
            pass

    for fmt in (
            "%d.%m.%Y",
            "%Y.%m.%d",
            "%d-%m-%Y",
            "%Y/%m/%d",
    ):
        match = re.search(r"\d{1,4}[./-]\d{1,2}[./-]\d{1,4}", text)

        if not match:
            continue

        try:
            return datetime.strptime(match.group(0), fmt).date()
        except ValueError:
            continue

    ru_match = re.search(
        r"(\d{1,2})\s+([а-яё]+)(?:\s+(\d{4}))?",
        text,
    )

    if ru_match:
        day, month_name, year = ru_match.groups()
        month = RU_MONTHS.get(month_name)

        if month:
            try:
                return date(
                    int(year) if year else today.year,
                    month,
                    int(day),
                )
            except ValueError:
                return None

    return None


def _common_conditions(city, area):
    conditions = []
    params = []

    if _is_selected(city):
        conditions.append("LOWER(city) = LOWER(%s)")
        params.append(city)

    if _is_selected(area):
        conditions.append(
            """
            (
                LOWER(BTRIM(COALESCE(district, ''))) = 'все'
                OR LOWER(COALESCE(district, '')) LIKE %s
            )
            """
        )
        params.append(f"%{str(area).lower()}%")

    return conditions, params


def _where_sql(conditions: Iterable[str]) -> sql.SQL:
    conditions = list(conditions)

    if not conditions:
        return sql.SQL("")

    return sql.SQL("WHERE " + " AND ".join(conditions))


def _fetch_event_rows(parser_key: str, conditions, params) -> List[dict]:
    parser_info = (
            MAIN_EVENT_DATABASES.get(parser_key)
            or TOUR_DATABASES.get(parser_key)
    )
    table_name = parser_info["table"]

    query = sql.SQL(
        """
        SELECT
            title,
            address,
            event_date,
            start_time,
            end_time,
            price,
            link,
            district,
            city
        FROM {table}
        {where_sql}
        ORDER BY event_date ASC NULLS LAST,
                 start_time ASC NULLS LAST,
                 title ASC
        """
    ).format(
        table=sql.Identifier(table_name),
        where_sql=_where_sql(conditions),
    )

    return _execute_rows(parser_key, query, params)


def _fetch_coworking_rows(parser_key: str, conditions, params) -> List[dict]:
    table_name = COWORKING_DATABASES[parser_key]["table"]

    query = sql.SQL(
        """
        SELECT
            name AS title,
            address,
            NULL::date AS event_date,
            NULL::text AS start_time,
            NULL::text AS end_time,
            NULL::text AS price,
            url AS link,
            schedule,
            district,
            city
        FROM {table}
        {where_sql}
        ORDER BY title ASC
        """
    ).format(
        table=sql.Identifier(table_name),
        where_sql=_where_sql(conditions),
    )

    return _execute_rows(parser_key, query, params)


def _execute_rows(parser_key: str, query, params) -> List[dict]:
    conn = connect_parser_db(parser_key)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            rows = [dict(row) for row in cur.fetchall()]

            for row in rows:
                row["source"] = parser_key

            return rows
    finally:
        conn.close()


def _selected_dates_for_kuda(event_date) -> List[date]:
    normalized_date = normalize_date(event_date)

    if normalized_date:
        return [normalized_date]

    today = date.today()
    return [today, today + timedelta(days=1)]


def _row_matches_kuda_dates(row: dict, event_date) -> bool:
    selected_dates = _selected_dates_for_kuda(event_date)

    start_date = (
            _parse_date_value(row.get("start_time"))
            or _parse_date_value(row.get("event_date"))
    )
    end_date = _parse_date_value(row.get("end_time")) or start_date

    if not start_date:
        return False

    if end_date and end_date < start_date:
        end_date = start_date

    return any(
        start_date <= selected_date <= (end_date or start_date)
        for selected_date in selected_dates
    )


def _prepare_kuda_row(row: dict) -> dict:
    row = dict(row)
    row["_sort_date"] = (
            _parse_date_value(row.get("start_time"))
            or _parse_date_value(row.get("event_date"))
            or date.max
    )
    row["date_range_start"] = row.get("start_time") or row.get("event_date")
    row["date_range_end"] = row.get("end_time")
    row["event_date"] = None
    row["start_time"] = None
    row["end_time"] = None
    return row


def _get_kudaekb_events(city, area, event_date) -> List[dict]:
    conditions, params = _common_conditions(city, area)
    rows = _fetch_event_rows("kudaekb_free", conditions, params)

    return [
        _prepare_kuda_row(row)
        for row in rows
        if _row_matches_kuda_dates(row, event_date)
    ]


def _get_regular_events(parser_key: str, city, area, event_date) -> List[dict]:
    conditions, params = _common_conditions(city, area)
    normalized_date = normalize_date(event_date)

    if normalized_date:
        if parser_key == "yandex_afisha":
            conditions.append("(event_date = %s OR event_date IS NULL)")
        else:
            conditions.append("event_date = %s")

        params.append(normalized_date)

    return _fetch_event_rows(parser_key, conditions, params)


def _get_tour_events(parser_key: str, city, area, event_date) -> List[dict]:
    conditions, params = _common_conditions(city, area)
    normalized_date = normalize_date(event_date)

    if normalized_date:
        conditions.append("(event_date = %s OR event_date IS NULL)")
        params.append(normalized_date)

    return _fetch_event_rows(parser_key, conditions, params)


def _sort_date(item: dict) -> date:
    return (
            item.get("_sort_date")
            or _parse_date_value(item.get("event_date"))
            or _parse_date_value(item.get("date_range_start"))
            or date.max
    )


def _sort_events(events: List[dict]) -> List[dict]:
    return sorted(
        events,
        key=lambda item: (
            _sort_date(item),
            item.get("start_time") or "99:99",
            item.get("title") or "",
        ),
    )


def _sort_by_title(rows: List[dict]) -> List[dict]:
    return sorted(rows, key=lambda item: item.get("title") or "")


def get_main_events(*, city: str = "Екатеринбург", area: str = "Любой район", event_date: str = None) -> List[dict]:
    all_events: List[dict] = []

    for parser_key in MAIN_EVENT_DATABASES:
        try:
            if parser_key == "kudaekb_free":
                rows = _get_kudaekb_events(city, area, event_date)
            else:
                rows = _get_regular_events(parser_key, city, area, event_date)

            all_events.extend(rows)
        except Exception as e:
            print(f"Ошибка при запросе {parser_key}: {e}")

    return _sort_events(all_events)


def get_coworkings_by_filters(*, city: str = "Екатеринбург", area: str = "Любой район") -> List[dict]:
    rows: List[dict] = []

    for parser_key in COWORKING_DATABASES:
        try:
            conditions, params = _common_conditions(city, area)
            rows.extend(_fetch_coworking_rows(parser_key, conditions, params))
        except Exception as e:
            print(f"Ошибка при запросе {parser_key}: {e}")

    return _sort_by_title(rows)


def get_tours_by_filters(*, city: str = "Екатеринбург", area: str = "Любой район", event_date: str = None) -> List[
    dict]:
    rows: List[dict] = []

    for parser_key in TOUR_DATABASES:
        try:
            rows.extend(_get_tour_events(parser_key, city, area, event_date))
        except Exception as e:
            print(f"Ошибка при запросе {parser_key}: {e}")

    return _sort_events(rows)


def get_events_by_filters(*, city: str = "Екатеринбург", area: str = "Любой район", event_date: str = None,
                          section: str = "main", limit: int | None = None) -> List[dict]:
    if section == "coworking":
        rows = get_coworkings_by_filters(city=city, area=area)
    elif section == "tours":
        rows = get_tours_by_filters(
            city=city,
            area=area,
            event_date=event_date,
        )
    else:
        rows = get_main_events(
            city=city,
            area=area,
            event_date=event_date,
        )

    if limit is not None:
        return rows[:limit]

    return rows
