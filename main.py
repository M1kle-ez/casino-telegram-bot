import asyncio
import random
import sqlite3
import time
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# Инициализируем бота и диспетчер
BOT_TOKEN = "8631506205:AAHjmCHYv6-x9eGy31pgsiydtx__ulRF8-Q"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- РАБОТА С БАЗОЙ ДАННЫХ SQLite ---
DB_NAME = "casino_game.db"

# --- ЗАЩИТА ОТ СПАМА (КЛИКЕРА) ---
# Словарь для хранения времени последнего клика {user_id: timestamp}
CLICK_COOLDOWNS = {}
# Время задержки между кликами в секундах
CLICK_DELAY = 1


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 100
        )
    ''')
    conn.commit()
    conn.close()


def get_user_balance(user_id, username):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    if result is None:
        cursor.execute("INSERT INTO users (user_id, username, balance) VALUES (?, ?, ?)", (user_id, username, 100))
        conn.commit()
        balance = 100
    else:
        balance = result[0]
        cursor.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
        conn.commit()

    conn.close()
    return balance


def update_user_balance(user_id, new_balance):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
    conn.commit()
    conn.close()


def get_top_players():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 10")
    top = cursor.fetchall()
    conn.close()
    return top


# Инициализируем БД при запуске
init_db()


# --- СОСТОЯНИЯ И МЕНЮ ИГРЫ ---
class CasinoStates(StatesGroup):
    waiting_for_deps = State()
    main_menu = State()
    clicker_menu = State()
    waiting_for_dep_amount = State()
    waiting_for_color = State()


def get_main_menu():
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="🎰 ДЭП"))
    builder.add(types.KeyboardButton(text="💰 Баланс"))
    builder.add(types.KeyboardButton(text="💼 Заработать"))
    builder.add(types.KeyboardButton(text="🏆 Топ лудоманов"))
    builder.add(types.KeyboardButton(text="🛒 Магазин Звёзд"))
    builder.adjust(1, 2, 1, 1)
    return builder.as_markup(resize_keyboard=True)


def get_back_menu():
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="⬅️ Назад в меню"))
    return builder.as_markup(resize_keyboard=True)


def get_color_menu():
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="🔴 Красный"))
    builder.add(types.KeyboardButton(text="⚫️ Черный"))
    builder.add(types.KeyboardButton(text="🟢 Зеленый"))
    builder.add(types.KeyboardButton(text="⬅️ Назад в меню"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


# 1. КОМАНДА /START
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    username = message.from_user.username or message.from_user.first_name
    get_user_balance(message.from_user.id, username)

    await message.answer(
        f"Добро пожаловать в симулятор главного лудомана района! 🎰\n\n"
        "Признавайся честно: **сколько раз ты уже дэпал в казик?** 💸"
    )
    await state.set_state(CasinoStates.waiting_for_deps)


# 2. ПОЛУЧЕНИЕ ПЕРВОГО ОТВЕТА
@dp.message(CasinoStates.waiting_for_deps)
async def process_deps_count(message: types.Message, state: FSMContext):
    username = message.from_user.username or message.from_user.first_name
    balance = get_user_balance(message.from_user.id, username)

    await message.answer(
        f"Понял, зафиксировал ответ: «{message.text}». Обратного пути нет! 😈\n"
        f"Твой баланс: **{balance}$**\n\n"
        "Перед тобой главное меню. Выбирай действие:",
        reply_markup=get_main_menu()
    )
    await state.set_state(CasinoStates.main_menu)


# --- КНОПКА: БАЛАНС (Работает в любом состоянии) ---
@dp.message(lambda message: message.text == "💰 Баланс")
async def press_balance(message: types.Message, state: FSMContext):
    await state.set_state(CasinoStates.main_menu)
    username = message.from_user.username or message.from_user.first_name
    balance = get_user_balance(message.from_user.id, username)
    await message.answer(f"💳 Твой текущий баланс: **{balance}$**", reply_markup=get_back_menu())


# --- КНОПКА: ТОП ЛУДОМАНОВ (Работает в любом состоянии) ---
@dp.message(lambda message: message.text == "🏆 Топ лудоманов")
async def press_top(message: types.Message, state: FSMContext):
    await state.set_state(CasinoStates.main_menu)
    top_list = get_top_players()
    text = "🏆 **ТОП-10 ГЛАВНЫХ ЛУДОМАНОВ:**\n\n"
    for index, player in enumerate(top_list, start=1):
        username, balance = player
        text += f"{index}. @{username} — **{balance}$**\n"
    await message.answer(text)


# --- КНОПКА НАЗАД В ГЛАВНОЕ МЕНЮ ---
@dp.message(lambda message: message.text == "⬅️ Назад в меню")
async def go_back_to_menu(message: types.Message, state: FSMContext):
    await message.answer("Вы вернулись в главное меню.", reply_markup=get_main_menu())
    await state.set_state(CasinoStates.main_menu)


# --- КНОПКА: ЗАРАБОТАТЬ / КЛИКЕР (Работает в любом состоянии) ---
@dp.message(lambda message: message.text == "💼 Заработать")
async def press_earn(message: types.Message, state: FSMContext):
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="⚡️ КЛИК!"))
    builder.add(types.KeyboardButton(text="⬅️ Назад в меню"))
    builder.adjust(1)

    await message.answer(
        "Добро пожаловать на работу! 💼\nКликай по кнопке ниже, чтобы зарабатывать кэш.",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )
    await state.set_state(CasinoStates.clicker_menu)


# Обработчик клика с проверкой задержки времени
@dp.message(CasinoStates.clicker_menu, lambda message: message.text == "⚡️ КЛИК!")
async def press_click(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    current_time = time.time()

    # Проверяем, нажимал ли пользователь кнопку ранее
    if user_id in CLICK_COOLDOWNS:
        last_click_time = CLICK_COOLDOWNS[user_id]
        time_passed = current_time - last_click_time

        # Если прошло меньше секунд, чем настроено в CLICK_DELAY
        if time_passed < CLICK_DELAY:
            time_left = int(CLICK_DELAY - time_passed) + 1
            await message.answer(f"⏳ Не спамь! Сервер устал. Подожди ещё **{time_left} сек.** перед следующим кликом.")
            return

    # Если проверка пройдена, обновляем время последнего клика
    CLICK_COOLDOWNS[user_id] = current_time

    username = message.from_user.username or message.from_user.first_name
    current_balance = get_user_balance(user_id, username)

    earned = random.randint(1, 3)
    new_balance = current_balance + earned

    update_user_balance(user_id, new_balance)
    await message.answer(f"➕ Заработано: **{earned}$**\n💰 Текущий баланс: **{new_balance}$**")


# --- КНОПКА: МАГАЗИН ЗВЁЗД (Работает в любом состоянии) ---
@dp.message(lambda message: message.text == "🛒 Магазин Звёзд")
async def open_shop(message: types.Message, state: FSMContext):
    await state.set_state(CasinoStates.main_menu)
    inline_builder = InlineKeyboardBuilder()
    inline_builder.add(types.InlineKeyboardButton(text="⭐ 100$ за 1 Звезду", callback_data="buy_stars_100"))
    inline_builder.add(types.InlineKeyboardButton(text="⭐ 500$ за 5 Звёзд", callback_data="buy_stars_500"))
    inline_builder.add(types.InlineKeyboardButton(text="⭐ 1000$ за 10 Звёзд", callback_data="buy_stars_1000"))
    inline_builder.add(types.InlineKeyboardButton(text="⭐ 5000$ за 50 Звёзд", callback_data="buy_stars_5000"))
    inline_builder.adjust(1)

    await message.answer(
        "🛒 **МАГАЗИН ИГРОВЫХ ФИШЕК ЗА TELEGRAM STARS**\n\nВыбери пакет для покупки:",
        reply_markup=inline_builder.as_markup()
    )


# Выставление счета в XTR (Telegram Stars) при клике
@dp.callback_query(lambda callback: callback.data.startswith("buy_stars_"))
async def send_stars_invoice(callback: types.CallbackQuery):
    await callback.answer()
    chips_amount = int(callback.data.split("_")[-1])
    stars_price = chips_amount // 100

    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=f"💰 Пакет фишек: +{chips_amount}$",
        description=f"Пополнение баланса симулятора казино на {chips_amount}$ фишек.",
        payload=f"stars_chips_{chips_amount}",
        currency="XTR",
        prices=[
            types.LabeledPrice(label="Оплата Звёздами", amount=stars_price)
        ],
        provider_token=""
    )


@dp.pre_checkout_query()
async def process_stars_pre_checkout(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@dp.message(lambda message: message.successful_payment is not None)
async def success_stars_payment(message: types.Message, state: FSMContext):
    payment = message.successful_payment
    payload = payment.invoice_payload

    if payload.startswith("stars_chips_"):
        chips_to_add = int(payload.split("_")[-1])
        username = message.from_user.username or message.from_user.first_name
        current_balance = get_user_balance(message.from_user.id, username)

        new_balance = current_balance + chips_to_add
        update_user_balance(message.from_user.id, new_balance)

        await message.answer(
            f"🎉 Оплата успешно завершена! Вы потратили **{payment.total_amount}** ⭐️\n"
            f"💰 На баланс начислено **{chips_to_add}$** игровых фишек!\n"
            f"Текущий баланс: **{new_balance}$**",
            reply_markup=get_main_menu()
        )
        await state.set_state(CasinoStates.main_menu)


# --- КНОПКА: ДЭП (Работает в любом состоянии) ---
@dp.message(lambda message: message.text == "🎰 ДЭП")
async def press_dep(message: types.Message, state: FSMContext):
    username = message.from_user.username or message.from_user.first_name
    balance = get_user_balance(message.from_user.id, username)

    await message.answer(
        f"Ваш баланс: **{balance}$**\n\nВведите сумму вашего дэпа (ставки):",
        reply_markup=get_back_menu()
    )
    await state.set_state(CasinoStates.waiting_for_dep_amount)


# Логика ввода суммы ставки
@dp.message(CasinoStates.waiting_for_dep_amount)
async def process_dep_amount(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад в меню":
        await go_back_to_menu(message, state)
        return

    if not message.text.isdigit():
        await message.answer("❌ Введи корректную сумму числом:")
        return

    bet = int(message.text)
    username = message.from_user.username or message.from_user.first_name
    balance = get_user_balance(message.from_user.id, username)

    if bet <= 0:
        await message.answer("❌ Ставка должна быть больше 0. Введи сумму:")
        return
    if bet > balance:
        await message.answer(f"❌ Недостаточно средств! Твой баланс: {balance}$. Введи сумму меньше:")
        return

    await state.update_data(current_bet=bet)
    await message.answer(f"Ставка **{bet}$** принята!\nВыбери цвет:", reply_markup=get_color_menu())
    await state.set_state(CasinoStates.waiting_for_color)


# --- КНОПКА: ПОВТОР СТАВКИ (Работает в любом состоянии) ---
@dp.message(lambda message: message.text == "🔄 Повторить ставку")
async def press_repeat_bet(message: types.Message, state: FSMContext):
    data = await state.get_data()
    last_bet = data.get("current_bet", 0)
    username = message.from_user.username or message.from_user.first_name
    balance = get_user_balance(message.from_user.id, username)

    if last_bet == 0:
        await message.answer("❌ Нет прошлой ставки! Сделайте обычный ДЭП.")
        return
    if last_bet > balance:
        await message.answer(f"❌ Недостаточно средств для повтора ставки в **{last_bet}$**! Баланс: **{balance}$**.")
        return

    await message.answer(f"Повторяем ставку **{last_bet}$**!\nВыбери новый цвет:", reply_markup=get_color_menu())
    await state.set_state(CasinoStates.waiting_for_color)


# ОБРАБОТКА ВЫБОРА ЦВЕТА И РУЛЕТКА
@dp.message(CasinoStates.waiting_for_color)
async def process_color_choice(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад в меню":
        await go_back_to_menu(message, state)
        return

    chosen_color = message.text
    if chosen_color not in ["🔴 Красный", "⚫️ Черный", "🟢 Зеленый"]:
        await message.answer("❌ Выбери цвет с помощью кнопок!")
        return

    data = await state.get_data()
    bet = data.get("current_bet", 0)
    username = message.from_user.username or message.from_user.first_name
    balance = get_user_balance(message.from_user.id, username)

    roll = random.uniform(0, 100)
    if roll <= 1.0:
        winning_color = "🟢 Зеленый"
    elif roll <= 50.5:
        winning_color = "🔴 Красный"
    else:
        winning_color = "⚫️ Черный"

    await message.answer(f"🎰 Крутим рулетку... Выпадает: **{winning_color}**!")

    if chosen_color == winning_color:
        if winning_color == "🟢 Зеленый":
            win_amount = bet * 25
            new_balance = balance + (win_amount - bet)
            await message.answer(f"🔥 НЕВЕРОЯТНО! Ты угадал Зеленый! Выигрыш: **{win_amount}$** (x25)! 🎉")
        else:
            win_amount = bet * 2
            new_balance = balance + (win_amount - bet)
            await message.answer(f"💵 Поздравляем! Твой цвет выиграл! Выигрыш: **{win_amount}$** (x2)!")
    else:
        new_balance = balance - bet
        await message.answer(f"😭 Увы, мимо! Твоя ставка **{bet}$** сгорела.")

    update_user_balance(message.from_user.id, new_balance)

    end_builder = ReplyKeyboardBuilder()
    end_builder.add(types.KeyboardButton(text="🔄 Повторить ставку"))
    end_builder.add(types.KeyboardButton(text="🎰 ДЭП"))
    end_builder.add(types.KeyboardButton(text="💰 Баланс"))
    end_builder.add(types.KeyboardButton(text="💼 Заработать"))
    end_builder.adjust(1, 2)

    await message.answer(
        f"💰 Твой баланс теперь: **{new_balance}$**\n"
        f"Хочешь крутануть еще раз с той же ставкой (**{bet}$**)?",
        reply_markup=end_builder.as_markup(resize_keyboard=True)
    )
    await state.set_state(CasinoStates.main_menu)


# АСИНХРОННЫЙ ЗАПУСК
async def main():
    print("Казино с донатом через Telegram Stars успешно запущено...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
