from datetime import datetime

from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db_movements.db_find_events import get_events_by_filters

from . import texts
from .keyboards import (
    AREA_NAMES,
    CITY_NAMES,
    AreaCallback,
    CityCallback,
    DateCallback,
    MenuCallback,
    NavCallback,
    ResultCallback,
    areas_keyboard,
    back_to_main_butt,
    cities_keyboard,
    date_keyboard,
    main_menu_keyboard,
    manual_date_back_keyboard,
    results_keyboard,
)

router = Router()


class Form(StatesGroup):
    city = State()
    area = State()
    date = State()
    manual_date = State()


async def _delete_message_safe(message: types.Message | None) -> None:
    if not message:
        return

    try:
        await message.delete()
    except TelegramBadRequest:
        pass


async def _delete_last_bot_message(state: FSMContext, bot, chat_id: int) -> None:
    data = await state.get_data()
    message_id = data.get("last_bot_message_id")

    if not message_id:
        return

    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramBadRequest:
        pass


async def _send_step_message(*, state: FSMContext, target_message: types.Message | None, bot, chat_id: int, text: str,
                             reply_markup=None, ) -> types.Message:
    if target_message:
        await _delete_message_safe(target_message)

    await _delete_last_bot_message(state, bot, chat_id)

    sent_message = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
    )

    await state.update_data(last_bot_message_id=sent_message.message_id)

    return sent_message


def _result_context_from_state(data: dict) -> dict:
    last_result = data.get("last_result") or {}

    return {
        "city": last_result.get("city", data.get("city", "Екатеринбург")),
        "area": last_result.get("area", data.get("area", "Любой район")),
        "date": last_result.get("date", data.get("date", "Любая дата")),
    }


async def _edit_or_send_result_message(*, state: FSMContext, bot, chat_id: int, target_message: types.Message | None,
                                       text: str, reply_markup) -> types.Message:
    if target_message:
        try:
            await target_message.edit_text(
                text=text,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
                parse_mode="HTML",
            )
            await state.update_data(
                last_bot_message_id=target_message.message_id,
            )
            return target_message
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                await state.update_data(
                    last_bot_message_id=target_message.message_id,
                )
                return target_message

            await _delete_message_safe(target_message)

    sent_message = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        disable_web_page_preview=True,
        parse_mode="HTML",
    )

    await state.update_data(last_bot_message_id=sent_message.message_id)

    return sent_message


async def _show_results_page(*, state: FSMContext, bot, chat_id: int, target_message: types.Message | None = None,
                             section: str = "main", page: int = 0) -> None:
    data = await state.get_data()
    result_context = _result_context_from_state(data)

    city = result_context["city"]
    area = result_context["area"]
    date_str = result_context["date"]

    events = get_events_by_filters(
        city=city,
        area=area,
        event_date=date_str,
        section=section,
    )

    text, safe_page, total_pages = texts.format_results_page(
        events=events,
        city=city,
        area=area,
        date_str=date_str,
        section=section,
        page=page,
    )

    reply_markup = results_keyboard(
        section=section,
        page=safe_page,
        total_pages=total_pages,
    )

    await _edit_or_send_result_message(
        state=state,
        bot=bot,
        chat_id=chat_id,
        target_message=target_message,
        text=text,
        reply_markup=reply_markup,
    )

    await state.update_data(
        last_result=result_context,
        current_result_section=section,
        current_result_page=safe_page,
        current_result_total_pages=total_pages,
    )


async def _finish_search_and_show_results(*, state: FSMContext, bot, chat_id: int) -> None:
    data = await state.get_data()

    result_data = {
        "city": data.get("city", "Екатеринбург"),
        "area": data.get("area", "Любой район"),
        "date": data.get("date", "Любая дата"),
    }

    await _delete_last_bot_message(state, bot, chat_id)
    await state.clear()
    await state.update_data(last_result=result_data)

    await _show_results_page(
        state=state,
        bot=bot,
        chat_id=chat_id,
        section="main",
        page=0,
    )


async def _start_new_search(*, state: FSMContext, bot, chat_id: int) -> None:
    await state.clear()
    await state.set_state(Form.city)

    sent_message = await bot.send_message(
        chat_id=chat_id,
        text=texts.step_pick_city(),
        reply_markup=cities_keyboard(),
    )

    await state.update_data(
        last_bot_message_id=sent_message.message_id,
    )


@router.message(CommandStart())
async def start_handler(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        texts.MAIN_MENU_TEXT,
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(MenuCallback.filter(F.action == "search"))
async def search_start(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()

    if not callback.message:
        return

    await state.clear()
    await _delete_message_safe(callback.message)
    await _start_new_search(
        state=state,
        bot=callback.bot,
        chat_id=callback.from_user.id,
    )


@router.callback_query(MenuCallback.filter(F.action == "about"))
async def about_handler(callback: types.CallbackQuery) -> None:
    if not callback.message:
        return

    await callback.answer()
    await callback.message.answer(
        text=texts.ABOUT_TEXT,
        reply_markup=back_to_main_butt(),
    )
    await _delete_message_safe(callback.message)


@router.callback_query(MenuCallback.filter(F.action == "help"))
async def help_handler(callback: types.CallbackQuery) -> None:
    if not callback.message:
        return

    await callback.answer()
    await callback.message.answer(
        text=texts.HELP_TEXT,
        reply_markup=back_to_main_butt(),
    )
    await _delete_message_safe(callback.message)


@router.callback_query(CityCallback.filter(), Form.city)
async def choose_city(
        callback: types.CallbackQuery,
        callback_data: CityCallback,
        state: FSMContext,
) -> None:
    if not callback.message:
        return

    city_code = callback_data.code
    city_name = CITY_NAMES[city_code]

    if city_code != "ekb":
        await callback.answer(
            texts.city_in_development_alert(city_name),
            show_alert=True,
        )
        return

    await callback.answer()

    await state.update_data(
        city_code=city_code,
        city=city_name,
    )
    await state.set_state(Form.area)

    await _send_step_message(
        state=state,
        target_message=callback.message,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text=texts.step_pick_area(city_name),
        reply_markup=areas_keyboard(city_code),
    )


@router.callback_query(AreaCallback.filter(), Form.area)
async def choose_area(callback: types.CallbackQuery, callback_data: AreaCallback, state: FSMContext) -> None:
    await callback.answer()
    if not callback.message:
        return

    area_name = AREA_NAMES.get(callback_data.code)

    if not area_name:
        return

    await state.update_data(area=area_name)
    data = await state.get_data()
    await state.set_state(Form.date)

    await _send_step_message(
        state=state,
        target_message=callback.message,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text=texts.step_pick_date(
            data.get("city", ""),
            area_name,
        ),
        reply_markup=date_keyboard(),
    )


@router.callback_query(NavCallback.filter(F.to == "skip_area"), Form.area)
async def skip_area(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()

    if not callback.message:
        return

    await state.update_data(area="Любой район")
    data = await state.get_data()
    await state.set_state(Form.date)

    await _send_step_message(
        state=state,
        target_message=callback.message,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text=texts.step_pick_date(
            data.get("city", ""),
            "Любой район",
        ),
        reply_markup=date_keyboard(),
    )


@router.callback_query(DateCallback.filter(), Form.date)
async def choose_date(callback: types.CallbackQuery, callback_data: DateCallback, state: FSMContext) -> None:
    await callback.answer()
    if not callback.message:
        return

    if callback_data.value == "manual":
        await state.set_state(Form.manual_date)

        await _send_step_message(
            state=state,
            target_message=callback.message,
            bot=callback.bot,
            chat_id=callback.message.chat.id,
            text=texts.DATE_MANUAL_PROMPT,
            reply_markup=manual_date_back_keyboard(),
        )
        return

    await state.update_data(date=callback_data.value)

    await _finish_search_and_show_results(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
    )


@router.callback_query(NavCallback.filter(F.to == "back_to_date"), Form.manual_date)
async def back_to_date_selection(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if not callback.message:
        return

    await state.set_state(Form.date)
    data = await state.get_data()

    await _send_step_message(
        state=state,
        target_message=callback.message,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text=texts.step_pick_date(
            data.get("city", ""),
            data.get("area", "Любой район"),
        ),
        reply_markup=date_keyboard(),
    )


@router.callback_query(NavCallback.filter(F.to == "skip_date"), Form.date)
async def skip_date(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if not callback.message:
        return

    await state.update_data(date="Любая дата")

    await _finish_search_and_show_results(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
    )


@router.message(Form.manual_date)
async def process_manual_date(message: types.Message, state: FSMContext) -> None:
    await _delete_message_safe(message)

    user_input = (message.text or "").strip()

    try:
        parsed_date = datetime.strptime(user_input, "%d.%m.%Y")
        date_for_db = parsed_date.strftime("%Y.%m.%d")
    except ValueError:
        await _delete_last_bot_message(state, message.bot, message.chat.id)

        sent_message = await message.bot.send_message(
            chat_id=message.chat.id,
            text=texts.DATE_INVALID,
            reply_markup=manual_date_back_keyboard(),
        )
        await state.update_data(last_bot_message_id=sent_message.message_id)
        return

    await state.update_data(date=date_for_db)

    await _finish_search_and_show_results(
        state=state,
        bot=message.bot,
        chat_id=message.chat.id,
    )


@router.callback_query(ResultCallback.filter())
async def result_page_handler(callback: types.CallbackQuery, callback_data: ResultCallback, state: FSMContext) -> None:
    await callback.answer()
    if not callback.message:
        return

    data = await state.get_data()

    if not data.get("last_result"):
        await _delete_message_safe(callback.message)
        await _start_new_search(
            state=state,
            bot=callback.bot,
            chat_id=callback.from_user.id,
        )
        return

    await _show_results_page(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        target_message=callback.message,
        section=callback_data.section,
        page=callback_data.page,
    )


@router.callback_query(NavCallback.filter(F.to == "back_to_menu"))
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if callback.message:
        await _delete_message_safe(callback.message)

    await state.clear()

    await callback.bot.send_message(
        chat_id=callback.from_user.id,
        text=texts.MAIN_MENU_TEXT,
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(NavCallback.filter(F.to == "back_to_city"))
async def back_to_city(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if not callback.message:
        return

    await state.set_state(Form.city)

    await _send_step_message(
        state=state,
        target_message=callback.message,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text=texts.step_pick_city(),
        reply_markup=cities_keyboard(),
    )


@router.callback_query(NavCallback.filter(F.to == "back_to_area"))
async def back_to_area(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if not callback.message:
        return

    data = await state.get_data()
    await state.set_state(Form.area)

    await _send_step_message(
        state=state,
        target_message=callback.message,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text=texts.step_pick_area(data.get("city", "")),
        reply_markup=areas_keyboard(data.get("city_code", "ekb")),
    )


@router.callback_query(NavCallback.filter(F.to == "new_search"))
async def new_search(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if callback.message:
        await _delete_message_safe(callback.message)

    await _start_new_search(
        state=state,
        bot=callback.bot,
        chat_id=callback.from_user.id,
    )


@router.message()
async def unknown_message(message: types.Message, state: FSMContext) -> None:
    current_state = await state.get_state()

    if current_state is not None:
        await _delete_message_safe(message)
        return

    await message.answer(
        texts.UNKNOWN_USE_MENU,
        reply_markup=main_menu_keyboard(),
    )
