import asyncio
import logging
import gc
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiohttp import TCPConnector
from aiogram.client.bot import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from bot.main import main as run_bot_polling
from db_movements.db import get_database_label, init_db
from parsers.go_parser import run_go as parse_gorpom_coworkings
from parsers.kov_parser import runkov as parse_kovorkingi_online
from parsers.parser2 import parse_yeltsin_center_free_events
from parsers.parser3 import parse_calendar
from parsers.parser4 import parse_yandex_afisha
from parsers.parser5 import run as parse_kudaekb_free
from parsers.sputnik_parser import parse_page as parse_sputnik8
from aiogram import Bot


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

PARSERS = [
    ("Ельцин Центр", parse_yeltsin_center_free_events),
    ("Парк Маяковского", parse_calendar),
    ("Яндекс Афиша", parse_yandex_afisha),
    ("KudaEkb", parse_kudaekb_free),
    ("Sputnik8", parse_sputnik8),
    ("Kovorkingi.online", parse_kovorkingi_online),
    ("Gorpom.ru", parse_gorpom_coworkings),
]


async def _safe_parser_run(parser_name: str, parser_func):
    try:
        await asyncio.to_thread(parser_func)
    except Exception as exc:
        logger.exception("Ошибка в парсере %s: %s", parser_name, exc)
    finally:
        gc.collect()
        await asyncio.sleep(0.5)


async def run_parsers():
    for parser_name, parser_func in PARSERS:
        await _safe_parser_run(parser_name, parser_func)
    logger.info("Все парсеры завершены")
    await asyncio.sleep(2)
    gc.collect()


async def create_bot_with_limits(token: str):
    connector = TCPConnector(
        limit=50,
        limit_per_host=10,
        ttl_dns_cache=300,
        force_close=True,
        enable_cleanup_closed=True,
    )

    session = AiohttpSession(
        connector=connector,
        timeout=aiohttp.ClientTimeout(total=30, connect=10),
    )

    return Bot(
        token=token,
        session=session,
        default=DefaultBotProperties(parse_mode="HTML"),
    )


async def startup():
    logger.info("Инициализация БД")
    await asyncio.to_thread(init_db)
    logger.info("База данных подключена: %s", get_database_label())

    # Scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_parsers,
        CronTrigger(hour=0, minute=0),
        id="daily_parsers",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info("Scheduler запущен")

    asyncio.create_task(run_parsers())

    await run_bot_polling()


if __name__ == "__main__":
    try:
        asyncio.run(startup())
    except KeyboardInterrupt:
        logger.info("Проект остановлен")