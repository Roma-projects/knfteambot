from __future__ import annotations
import os
from datetime import date, datetime
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple
import psycopg2
from psycopg2 import sql as pgsql_sql
from psycopg2.extras import execute_values

PARSER_DATABASES: Dict[str, str] = {
    "yeltsin_center": "parser_yeltsin_center",
    "mayakovsky_park": "parser_mayakovsky_park",
    "yandex_afisha": "parser_yandex_afisha",
    "kudaekb_free": "parser_kudaekb_free",
    "sputnik8": "parser_sputnik8",
    "kovorkingi_online": "parser_kovorkingi_online",
    "gorpom": "parser_gorpom",
}

PARSER_TABLES: Dict[str, str] = {
    "yeltsin_center": "events_yeltsin",
    "mayakovsky_park": "events_mayakovsky",
    "yandex_afisha": "events_afisha",
    "kudaekb_free": "events_kudaekb",
    "sputnik8": "events_sputnik8",
    "kovorkingi_online": "kovorkingi_online",
    "gorpom": "coworkings_gorpom",
}

BASE_DIR = Path(__file__).resolve().parent.parent
_SQL_DIR = BASE_DIR / "sql"

EVENT_COLUMNS = [
    "start_time",
    "end_time",
    "event_date",
    "city",
    "price",
    "address",
    "title",
    "link",
    "district",
]

COWORKING_COLUMNS = [
    "name",
    "url",
    "address",
    "schedule",
    "district",
    "city",
]


def _conn_params(*, dbname: str) -> Dict[str, Any]:
    return {
        "host": os.environ.get("PGHOST", "localhost"),
        "port": int(os.environ.get("PGPORT", "5432")),
        "user": os.environ.get("PGUSER", "postgres"),
        "password": os.environ.get("PGPASSWORD", "111"),
        "dbname": dbname,
    }


def _connect_maintenance():
    return psycopg2.connect(
        **_conn_params(
            dbname=os.environ.get("PG_MAINTENANCE_DB", "postgres")
        )
    )


def connect_parser_db(parser_key: str):
    if parser_key not in PARSER_DATABASES:
        raise KeyError(
            f"Неизвестный парсер: {parser_key}. Допустимо: {list(PARSER_DATABASES)}"
        )

    return psycopg2.connect(
        **_conn_params(dbname=PARSER_DATABASES[parser_key])
    )


def _ensure_database_exists(dbname: str) -> None:
    conn = _connect_maintenance()

    try:
        conn.autocommit = True

        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (dbname,),
            )

            if cur.fetchone():
                return

            cur.execute(
                pgsql_sql.SQL("CREATE DATABASE {}").format(
                    pgsql_sql.Identifier(dbname)
                )
            )

    finally:
        conn.close()


def _apply_schema_sql(dbname: str) -> None:
    sql_path = _SQL_DIR / f"{dbname}.sql"

    if not sql_path.is_file():
        raise FileNotFoundError(f"Нет файла схемы: {sql_path}")

    ddl = sql_path.read_text(encoding="utf-8")

    with psycopg2.connect(**_conn_params(dbname=dbname)) as conn:
        conn.autocommit = True

        with conn.cursor() as cur:
            cur.execute(ddl)


def _apply_post_schema_migrations(dbname: str) -> None:
    with psycopg2.connect(**_conn_params(dbname=dbname)) as conn:
        conn.autocommit = True

        with conn.cursor() as cur:
            for table_name in PARSER_TABLES.values():
                try:
                    cur.execute(
                        f"ALTER TABLE IF EXISTS {table_name} DROP COLUMN IF EXISTS source;"
                    )
                except Exception:
                    pass


def init_db() -> None:
    for dbname in PARSER_DATABASES.values():
        _ensure_database_exists(dbname)
        _apply_schema_sql(dbname)
        _apply_post_schema_migrations(dbname)


def get_database_label() -> str:
    host = os.environ.get("PGHOST", "localhost")
    port = os.environ.get("PGPORT", "5432")
    user = os.environ.get("PGUSER", "postgres")

    names = ", ".join(sorted(PARSER_DATABASES.values()))

    return (
        f"PostgreSQL {host}:{port}, пользователь {user} | БД: {names}"
    )


def _truncate_then_values(
        conn,
        *,
        truncate_sql: str,
        insert_sql: str,
        rows: List[tuple],
        page_size: int = 500,
) -> None:
    with conn.cursor() as cur:
        cur.execute(truncate_sql)

        if rows:
            execute_values(
                cur,
                insert_sql,
                rows,
                page_size=page_size,
            )

    conn.commit()


def _clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None

    text = str(value).strip()

    return text or None


def _extract_start_end_time(
        raw_time: Any,
        *,
        fallback_start: Any = None,
        fallback_end: Any = None,
) -> Tuple[Optional[str], Optional[str]]:
    start = _clean_text(fallback_start)
    end = _clean_text(fallback_end)

    raw = _clean_text(raw_time)

    if not raw:
        return start, end

    time_matches = re.findall(
        r"\b([01]?\d|2[0-3]):([0-5]\d)\b",
        raw,
    )

    formatted = [
        f"{hh.zfill(2)}:{mm}"
        for hh, mm in time_matches
    ]

    if formatted:
        if not start:
            start = formatted[0]

        if len(formatted) > 1 and not end:
            end = formatted[1]

    return start, end


def _parse_event_date(raw_date: Any) -> Optional[date]:
    value = _clean_text(raw_date)

    if not value:
        return None

    normalized = value.split(",")[0].strip().lower()

    normalized = (
        normalized
        .replace(" г.", "")
        .replace(" года", "")
        .replace("  ", " ")
        .strip()
    )

    ru_months = {
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

    ru_match = re.match(
        r"^(\d{1,2})\s+([а-яё]+)\s+(\d{4})$",
        normalized,
    )

    if ru_match:
        day, month_name, year = ru_match.groups()

        month = ru_months.get(month_name)

        if month:
            try:
                return date(int(year), month, int(day))
            except ValueError:
                return None

    for fmt in (
            "%Y-%m-%d",
            "%d.%m.%Y",
            "%d-%m-%Y",
            "%Y/%m/%d",
    ):
        try:
            return datetime.strptime(normalized, fmt).date()
        except ValueError:
            continue

    return None


def _parse_yeltsin_center_date(raw_date: Any) -> date:
    value = _clean_text(raw_date)

    today = date.today()

    if not value:
        return today

    normalized = value.strip().lower()

    normalized = (
        normalized
        .replace(" г.", "")
        .replace(" года", "")
        .replace("  ", " ")
        .strip()
    )

    ru_months = {
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

    match = re.match(
        r"^(\d{1,2})\s+([а-яё]+)$",
        normalized,
    )

    if match:
        day, month_name = match.groups()

        month = ru_months.get(month_name)

        if month:
            try:
                return date(today.year, month, int(day))
            except ValueError:
                return today

    return today


def _normalize_row(event: Mapping[str, Any], parser_key: str) -> Dict[str, Any]:
    if parser_key == "yandex_afisha":
        return {
            "start_time": event.get("start_time"),
            "end_time": event.get("end_time"),
            "event_date": event.get("event_date"),
            "city": event.get("city", "Екатеринбург"),
            "price": event.get("price", "Бесплатно"),
            "address": event.get("address"),
            "title": event.get("title"),
            "link": event.get("link"),
            "district": event.get("district", "все"),
        }

    # Старая логика для остальных парсеров
    start_time, end_time = _extract_start_end_time(
        event.get("time"),
        fallback_start=event.get("start"),
        fallback_end=event.get("end"),
    )

    raw_date = (
            event.get("date")
            or event.get("event_date")
            or event.get("start")
    )

    if parser_key == "yeltsin_center":
        parsed_date = _parse_yeltsin_center_date(raw_date)
    else:
        parsed_date = _parse_event_date(raw_date)

    address = _clean_text(
        event.get("address")
        or event.get("location")
    )

    title = _clean_text(event.get("title"))

    link = _clean_text(
        event.get("link")
        or event.get("url")
        or event.get("details")
    )

    price = _clean_text(event.get("price")) or "Бесплатно"
    district = event.get("district") or "все"

    return {
        "start_time": start_time,
        "end_time": end_time,
        "event_date": parsed_date,
        "city": "Екатеринбург",
        "price": price,
        "address": address,
        "title": title,
        "link": link,
        "district": district,
    }


def _save_events(
        parser_key: str,
        events: Iterable[Mapping[str, Any]],
) -> None:
    normalized = [
        _normalize_row(event, parser_key)
        for event in events
    ]

    table_name = PARSER_TABLES[parser_key]

    rows: List[tuple] = []

    for row in normalized:
        if not row.get("title"):
            continue

        rows.append(
            (
                row["start_time"],
                row["end_time"],
                row["event_date"],
                row["city"],
                row["price"],
                row["address"],
                row["title"],
                row["link"],
                row["district"],
            )
        )

    columns = ", ".join(EVENT_COLUMNS)

    insert_sql = f"""
        INSERT INTO {table_name} (
            {columns}
        )
        VALUES %s
    """

    truncate_sql = f"TRUNCATE {table_name} RESTART IDENTITY;"

    with connect_parser_db(parser_key) as conn:
        _truncate_then_values(
            conn,
            truncate_sql=truncate_sql,
            insert_sql=insert_sql,
            rows=rows,
        )


def save_yeltsin_center_rows(events: Iterable[Mapping[str, Any]]) -> None:
    _save_events("yeltsin_center", events)


def save_mayakovsky_park_rows(events: Iterable[Mapping[str, Any]]) -> None:
    _save_events("mayakovsky_park", events)


def save_yandex_afisha_rows(events: Iterable[Mapping[str, Any]]) -> None:
    _save_events("yandex_afisha", events)


def save_kudaekb_free_rows(events: Iterable[Mapping[str, Any]]) -> None:
    _save_events("kudaekb_free", events)


def save_sputnik8_rows(events: Iterable[Mapping[str, Any]]) -> None:
    _save_events("sputnik8", events)


def _save_coworkings(
        parser_key: str,
        coworkings: Iterable[Mapping[str, Any]],
) -> None:
    table_name = PARSER_TABLES[parser_key]

    rows: List[tuple] = []

    for row in coworkings:
        name = _clean_text(row.get("name"))

        if not name:
            continue

        rows.append(
            (
                name,
                _clean_text(row.get("url")),
                _clean_text(row.get("address")),
                _clean_text(row.get("schedule")),
                row.get("district") or "все",
                "Екатеринбург",
            )
        )

    columns = ", ".join(COWORKING_COLUMNS)

    insert_sql = f"""
        INSERT INTO {table_name} (
            {columns}
        )
        VALUES %s
    """

    truncate_sql = f"TRUNCATE {table_name} RESTART IDENTITY;"

    with connect_parser_db(parser_key) as conn:
        _truncate_then_values(
            conn,
            truncate_sql=truncate_sql,
            insert_sql=insert_sql,
            rows=rows,
        )


def save_kovorkingi_online_rows(
        coworkings: Iterable[Mapping[str, Any]],
) -> None:
    _save_coworkings("kovorkingi_online", coworkings)


def save_gorpom_rows(
        coworkings: Iterable[Mapping[str, Any]],
) -> None:
    _save_coworkings("gorpom", coworkings)
