from __future__ import annotations
import re
from discrictfinder.street_index import STREET_TO_DISTRICT

STREET_PREFIX_PATTERN = re.compile(
    r"""
    \b(
        улица|
        ул|
        проспект|
        просп|
        пр|
        пр-т|
        переулок|
        пер|
        бульвар|
        бул|
        площадь|
        пл|
        набережная|
        наб|
        тракт|
        шоссе|
        проезд
    )\.?
    \b
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)

CITY_PATTERN = re.compile(
    r"\bекатеринбург\b",
    flags=re.IGNORECASE,
)

SERVICE_WORDS_PATTERN = re.compile(
    r"""
    \b(
        дом|
        д|
        офис|
        этаж|
        корпус|
        корп|
        строение|
        стр|
        помещение|
        пом|
        квартира|
        кв|
        подъезд|
        подъезд|
        секция
    )\.?
    \b
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)

HOUSE_NUMBER_PATTERN = re.compile(
    r"\b\d+[а-яa-z0-9/\-]*\b",
    flags=re.IGNORECASE,
)

NON_ALNUM_PATTERN = re.compile(
    r"[^а-яa-z0-9\s\-]"
)

MULTISPACE_PATTERN = re.compile(r"\s+")


def normalize_text(text: str | None) -> str:
    if not text:
        return ""

    text = text.lower()

    text = text.replace("ё", "е")
    text = CITY_PATTERN.sub(" ", text)
    text = STREET_PREFIX_PATTERN.sub(" ", text)
    text = SERVICE_WORDS_PATTERN.sub(" ", text)
    text = NON_ALNUM_PATTERN.sub(" ", text)
    text = HOUSE_NUMBER_PATTERN.sub(" ", text)
    text = MULTISPACE_PATTERN.sub(" ", text)

    return text.strip()


def get_possible_districts_by_address(address: str | None) -> list[str]:
    normalized = normalize_text(address)

    if not normalized:
        return []

    found_districts: set[str] = set()

    if normalized in STREET_TO_DISTRICT:
        found_districts.update(
            STREET_TO_DISTRICT[normalized]
        )

    if not found_districts:

        for street, districts in STREET_TO_DISTRICT.items():

            if street in normalized:
                found_districts.update(districts)
                continue

            if normalized in street:
                found_districts.update(districts)

    return sorted(found_districts)


def get_district_by_address(address: str | None) -> str:
    districts = get_possible_districts_by_address(address)

    if not districts:
        return "все"

    return ", ".join(districts)
