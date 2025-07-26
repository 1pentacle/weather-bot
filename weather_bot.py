import asyncio
import requests
from datetime import datetime, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = "8466883027:AAFF_ty8FP7bE78O2IAsPUDrLk_XqnR7DUM"
YANDEX_API_KEY = "cc6f05e0-ec91-4d06-9f10-597d93877b7a"
CITY_NAME = "Вятские Поляны"
LAT = 56.2284
LON = 51.0648
ADMIN_CHAT_ID = 8181234841  # Твой ID для отзывов

user_state = {}
user_notify_time = {}
user_rain_notify = {}
user_extreme_notify = {}

def get_weekday(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    return days[dt.weekday()]

def get_weather_data():
    url = f"https://api.weather.yandex.ru/v2/forecast?lat={LAT}&lon={LON}&lang=ru_RU"
    headers = {"X-Yandex-Weather-Key": YANDEX_API_KEY}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None
    return response.json()

def get_weather_advice(condition):
    rain_conditions = {"rain", "showers", "drizzle", "moderate-rain", "heavy-rain", "continuous-heavy-rain"}
    snow_conditions = {"snow", "light-snow", "wet-snow", "snow-showers", "hail"}
    thunder_conditions = {"thunderstorm", "thunderstorm-with-rain", "thunderstorm-with-hail"}

    if condition in rain_conditions:
        return "☔ Не забудьте взять зонт!"
    if condition in snow_conditions:
        return "❄️ Оденьтесь теплее, возможен снег."
    if condition in thunder_conditions:
        return "⚡ Осторожно, гроза!"
    return ""

def format_part_weather(part):
    conditions_dict = {
        "clear": "Ясно ☀️",
        "partly-cloudy": "Малооблачно 🌤",
        "cloudy": "Облачно ☁️",
        "overcast": "Пасмурно 🌥",
        "drizzle": "Морось 🌧",
        "light-rain": "Небольшой дождь 🌦",
        "rain": "Дождь 🌧",
        "moderate-rain": "Умеренный дождь 🌧",
        "heavy-rain": "Сильный дождь 🌧",
        "continuous-heavy-rain": "Продолжительный ливень 🌧",
        "showers": "Ливень 🌧",
        "wet-snow": "Мокрый снег 🌨",
        "light-snow": "Небольшой снег 🌨",
        "snow": "Снег ❄️",
        "snow-showers": "Снежные заряды ❄️",
        "hail": "Град 🌨",
        "thunderstorm": "Гроза ⛈",
        "thunderstorm-with-rain": "Дождь с грозой ⛈",
        "thunderstorm-with-hail": "Гроза с градом ⛈",
    }
    condition = part.get("condition", "unknown")
    desc = conditions_dict.get(condition, "Неизвестно")
    temp = part.get("temp_avg") or part.get("temp") or "—"
    humidity = part.get("humidity", "—")
    wind = part.get("wind_speed", "—")

    advice = get_weather_advice(condition)
    msg = (
        f"{desc}\n"
        f"🌡 Температура: {temp}°C\n"
        f"💧 Влажность: {humidity}%\n"
        f"🌬 Ветер: {wind} м/с\n"
    )
    if advice:
        msg += advice + "\n"
    return msg

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(CITY_NAME, callback_data="city_vyat")]
    ]
    markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text("Привет! Выберите город для прогноза погоды:", reply_markup=markup)
    elif update.callback_query:
        await update.callback_query.message.edit_text("Привет! Выберите город для прогноза погоды:", reply_markup=markup)
        await update.callback_query.answer()

    user_state[update.effective_chat.id] = None

async def show_forecast_menu(update: Update):
    keyboard = [
        [InlineKeyboardButton("Погода сейчас 🌤️", callback_data="forecast_now"),
         InlineKeyboardButton("Погода сегодня 📅", callback_data="forecast_today")],
        [InlineKeyboardButton("Погода завтра 🌥️", callback_data="forecast_tomorrow"),
         InlineKeyboardButton("Погода на неделю 📆", callback_data="forecast_week")],
        [InlineKeyboardButton("🕒 Уведомления", callback_data="notify_menu"),
         InlineKeyboardButton("📖 Помощь", callback_data="help_menu")],
        [InlineKeyboardButton("💬 Обратная связь", callback_data="feedback")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_city")]
    ]
    markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.edit_text(
        "**Выберите опцию:**",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    await update.callback_query.answer()

async def show_notify_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in user_rain_notify:
        user_rain_notify[chat_id] = False
    if chat_id not in user_extreme_notify:
        user_extreme_notify[chat_id] = True

    rain_notify = user_rain_notify.get(chat_id, False)
    extreme_notify = user_extreme_notify.get(chat_id, True)
    notify_time = user_notify_time.get(chat_id, None)
    notify_time_str = notify_time.strftime("%H:%M") if notify_time else "не установлено"

    keyboard = [
        [InlineKeyboardButton(f"{'✅' if rain_notify else '❌'} Уведомления о дожде ☔", callback_data="toggle_rain_notify")],
        [InlineKeyboardButton(f"{'✅' if extreme_notify else '❌'} Уведомления об экстремальной погоде ⚠️", callback_data="toggle_extreme_notify")],
        [InlineKeyboardButton("⏰ Установить время уведомления", callback_data="set_notify_time")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="forecast_menu_back")]
    ]
    markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.message.edit_text(
        f"**Настройки уведомлений:**\n\nВремя уведомления: {notify_time_str}\n",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    await update.callback_query.answer()

async def show_help_menu(update: Update):
    help_text = (
        "📖 *Помощь по боту*\n\n"
        "Я помогу вам узнать прогноз погоды в городе Вятские Поляны.\n\n"
        "Что умеет бот:\n"
        "- Показывать текущую погоду и прогноз на сегодня, завтра и неделю.\n"
        "- Настраивать уведомления о дожде и экстремальной погоде.\n"
        "- Удобное меню с кнопками для быстрого доступа.\n\n"
        "Использование:\n"
        "- Нажмите на город, чтобы выбрать.\n"
        "- Выберите нужный прогноз.\n"
        "- Настройте уведомления в разделе «🕒 Уведомления».\n"
        "- Обратитесь в «💬 Обратная связь», чтобы оставить отзыв.\n"
        "- В любой момент можно вернуться назад кнопкой «⬅️ Назад»."
    )
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="forecast_menu_back")]]
    markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.edit_text(help_text, parse_mode="Markdown", reply_markup=markup)
    await update.callback_query.answer()

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    chat_id = query.message.chat.id

    if data == "city_vyat":
        user_state[chat_id] = "forecast_menu"
        await show_forecast_menu(update)
    elif data == "back_to_city":
        user_state[chat_id] = None
        await start(update, context)
    elif data == "forecast_now":
        await send_forecast_now(update)
    elif data == "forecast_today":
        await send_forecast_day(update, 0)
    elif data == "forecast_tomorrow":
        await send_forecast_day(update, 1)
    elif data == "forecast_week":
        await send_forecast_week(update)
    elif data == "notify_menu":
        user_state[chat_id] = "notify_menu"
        await show_notify_menu(update, context)
    elif data == "toggle_rain_notify":
        user_rain_notify[chat_id] = not user_rain_notify.get(chat_id, False)
        await query.answer(f"Уведомления о дожде {'включены' if user_rain_notify[chat_id] else 'выключены'}.")
        await show_notify_menu(update, context)
    elif data == "toggle_extreme_notify":
        user_extreme_notify[chat_id] = not user_extreme_notify.get(chat_id, True)
        await query.answer(f"Уведомления об экстремальной погоде {'включены' if user_extreme_notify[chat_id] else 'выключены'}.")
        await show_notify_menu(update, context)
    elif data == "set_notify_time":
        user_state[chat_id] = "awaiting_notify_time"
        await query.message.reply_text("Введите время уведомления в формате ЧЧ:ММ (24-часовой формат), например 08:30")
        await query.answer()
    elif data == "forecast_menu_back":
        user_state[chat_id] = "forecast_menu"
        await show_forecast_menu(update)
    elif data == "help_menu":
        await show_help_menu(update)
    elif data == "feedback":
        user_state[chat_id] = "awaiting_feedback"
        await query.message.reply_text("Пожалуйста, оцените работу бота от 1 до 5 или напишите свой отзыв.")
        await query.answer()
    else:
        await query.answer("Неизвестная команда.", show_alert=True)

async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state = user_state.get(chat_id)

    if state == "awaiting_notify_time":
        text = update.message.text.strip()
        try:
            notify_time = datetime.strptime(text, "%H:%M").time()
            user_notify_time[chat_id] = notify_time
            user_state[chat_id] = "forecast_menu"
            await update.message.reply_text(f"Время уведомления установлено на {notify_time.strftime('%H:%M')}")
            await show_forecast_menu(update)
        except ValueError:
            await update.message.reply_text("Неверный формат времени. Пожалуйста, введите в формате ЧЧ:ММ, например 08:30.")
    elif state == "awaiting_feedback":
        text = update.message.text.strip()
        feedback_msg = (
            f"📝 Отзыв от пользователя {update.effective_user.full_name} "
            f"(@{update.effective_user.username or 'нет username'}, ID: {chat_id}):\n\n"
            f"{text}"
        )
        try:
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=feedback_msg)
            await update.message.reply_text("Спасибо за ваш отзыв! 🙏")
        except Exception:
            await update.message.reply_text("Произошла ошибка при отправке отзыва. Попробуйте позже.")
        user_state[chat_id] = "forecast_menu"
        await show_forecast_menu(update)
    else:
        await update.message.reply_text("Пожалуйста, используйте кнопки меню.")

async def send_forecast_now(update: Update):
    data = get_weather_data()
    if not data or "fact" not in data:
        await update.callback_query.message.edit_text("Ошибка при получении данных с Яндекс.Погоды.")
        return

    fact = data["fact"]
    condition = fact.get("condition", "unknown")
    conditions_dict = {
        "clear": "Ясно ☀️",
        "partly-cloudy": "Малооблачно 🌤",
        "cloudy": "Облачно ☁️",
        "overcast": "Пасмурно 🌥",
        "drizzle": "Морось 🌧",
        "light-rain": "Небольшой дождь 🌦",
        "rain": "Дождь 🌧",
        "moderate-rain": "Умеренный дождь 🌧",
        "heavy-rain": "Сильный дождь 🌧",
        "continuous-heavy-rain": "Продолжительный ливень 🌧",
        "showers": "Ливень 🌧",
        "wet-snow": "Мокрый снег 🌨",
        "light-snow": "Небольшой снег 🌨",
        "snow": "Снег ❄️",
        "snow-showers": "Снежные заряды ❄️",
        "hail": "Град 🌨",
        "thunderstorm": "Гроза ⛈",
        "thunderstorm-with-rain": "Дождь с грозой ⛈",
        "thunderstorm-with-hail": "Гроза с градом ⛈",
    }
    desc = conditions_dict.get(condition, "Неизвестно")
    temp = fact.get("temp", "N/A")
    feels_like = fact.get("feels_like", "N/A")
    humidity = fact.get("humidity", "N/A")
    wind = fact.get("wind_speed", "N/A")
    msg = (
        f"📍 *Погода в {CITY_NAME} сейчас:*\n"
        f"{desc}\n"
        f"🌡 Температура: {temp}°C (ощущается как {feels_like}°C)\n"
        f"💧 Влажность: {humidity}%\n"
        f"🌬 Ветер: {wind} м/с\n\n"
        f"⬅️ Чтобы вернуться назад — нажмите кнопку ниже."
    )
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="forecast_menu_back")]]
    markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.edit_text(msg, parse_mode="Markdown", reply_markup=markup)
    await update.callback_query.answer()

async def send_forecast_day(update: Update, day_index: int):
    data = get_weather_data()
    if not data or "forecasts" not in data:
        await update.callback_query.message.edit_text("Ошибка при получении данных с Яндекс.Погоды.")
        return

    forecasts = data["forecasts"]
    if day_index >= len(forecasts):
        await update.callback_query.message.edit_text("Прогноз на этот день недоступен.")
        return

    day_forecast = forecasts[day_index]
    date_str = day_forecast.get("date")
    weekday = get_weekday(date_str)

    sunrise = day_forecast.get("sunrise", "—")
    sunset = day_forecast.get("sunset", "—")

    parts_order = ["morning", "day", "evening", "night"]
    parts_names = ["Утро", "День", "Вечер", "Ночь"]

    msg = f"📅 *Прогноз погоды в {CITY_NAME} на {date_str} ({weekday}):*\n"
    msg += f"🌅 Рассвет: {sunrise}\n"
    msg += f"🌇 Закат: {sunset}\n"

    parts = day_forecast.get("parts", {})

    for part_key, part_name in zip(parts_order, parts_names):
        part = parts.get(part_key)
        if not part:
            continue
        msg += f"\n*{part_name}:*\n"
        msg += format_part_weather(part)

    msg += "\n⬅️ Чтобы вернуться назад — нажмите кнопку ниже."
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="forecast_menu_back")]]
    markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.edit_text(msg, parse_mode="Markdown", reply_markup=markup)
    await update.callback_query.answer()

async def send_forecast_week(update: Update):
    data = get_weather_data()
    if not data or "forecasts" not in data:
        await update.callback_query.message.edit_text("Ошибка при получении данных с Яндекс.Погоды.")
        return

    forecasts = data["forecasts"]
    if not forecasts:
        await update.callback_query.message.edit_text("Прогноз недоступен.")
        return

    msg = f"📅 *Прогноз погоды в {CITY_NAME} на неделю:*\n"

    for day in forecasts[:7]:
        date_str = day.get("date")
        weekday = get_weekday(date_str)
        parts = day.get("parts", {})
        day_part = parts.get("day")
        temp_day = day_part.get("temp_avg") if day_part else "—"
        condition = day_part.get("condition") if day_part else "unknown"

        conditions_dict = {
            "clear": "Ясно ☀️",
            "partly-cloudy": "Малооблачно 🌤",
            "cloudy": "Облачно ☁️",
            "overcast": "Пасмурно 🌥",
            "drizzle": "Морось 🌧",
            "light-rain": "Небольшой дождь 🌦",
            "rain": "Дождь 🌧",
            "moderate-rain": "Умеренный дождь 🌧",
            "heavy-rain": "Сильный дождь 🌧",
            "continuous-heavy-rain": "Продолжительный ливень 🌧",
            "showers": "Ливень 🌧",
            "wet-snow": "Мокрый снег 🌨",
            "light-snow": "Небольшой снег 🌨",
            "snow": "Снег ❄️",
            "snow-showers": "Снежные заряды ❄️",
            "hail": "Град 🌨",
            "thunderstorm": "Гроза ⛈",
            "thunderstorm-with-rain": "Дождь с грозой ⛈",
            "thunderstorm-with-hail": "Гроза с градом ⛈",
        }
        desc = conditions_dict.get(condition, "Неизвестно")
        msg += f"\n{date_str} ({weekday}): {desc}, температура днём {temp_day}°C"

    msg += "\n\n⬅️ Чтобы вернуться назад — нажмите кнопку ниже."
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="forecast_menu_back")]]
    markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.edit_text(msg, parse_mode="Markdown", reply_markup=markup)
    await update.callback_query.answer()


# --- НОВОЕ: Функция фоновых уведомлений ---
async def notify_users(app):
    while True:
        now = datetime.now().time().replace(second=0, microsecond=0)
        for chat_id, notify_time in user_notify_time.items():
            # Проверяем, включены ли уведомления (одна из двух)
            rain_enabled = user_rain_notify.get(chat_id, False)
            extreme_enabled = user_extreme_notify.get(chat_id, True)

            # Если время совпадает с установленным
            if notify_time == now:
                data = get_weather_data()
                if not data or "fact" not in data:
                    continue
                fact = data["fact"]
                condition = fact.get("condition", "unknown")
                temp = fact.get("temp", "N/A")
                humidity = fact.get("humidity", "N/A")
                wind = fact.get("wind_speed", "N/A")

                conditions_dict = {
                    "clear": "Ясно ☀️",
                    "partly-cloudy": "Малооблачно 🌤",
                    "cloudy": "Облачно ☁️",
                    "overcast": "Пасмурно 🌥",
                    "drizzle": "Морось 🌧",
                    "light-rain": "Небольшой дождь 🌦",
                    "rain": "Дождь 🌧",
                    "moderate-rain": "Умеренный дождь 🌧",
                    "heavy-rain": "Сильный дождь 🌧",
                    "continuous-heavy-rain": "Продолжительный ливень 🌧",
                    "showers": "Ливень 🌧",
                    "wet-snow": "Мокрый снег 🌨",
                    "light-snow": "Небольшой снег 🌨",
                    "snow": "Снег ❄️",
                    "snow-showers": "Снежные заряды ❄️",
                    "hail": "Град 🌨",
                    "thunderstorm": "Гроза ⛈",
                    "thunderstorm-with-rain": "Дождь с грозой ⛈",
                    "thunderstorm-with-hail": "Гроза с градом ⛈",
                }
                desc = conditions_dict.get(condition, "Неизвестно")

                messages = []

                if rain_enabled:
                    rain_conditions = {"rain", "showers", "drizzle", "moderate-rain", "heavy-rain", "continuous-heavy-rain"}
                    if condition in rain_conditions:
                        messages.append(f"☔ *Внимание! Дождь в {CITY_NAME}*\n{desc}\n🌡 Температура: {temp}°C\n💧 Влажность: {humidity}%\n🌬 Ветер: {wind} м/с\nНе забудьте взять зонт!")

                if extreme_enabled:
                    extreme_conditions = {"hail", "thunderstorm", "thunderstorm-with-rain", "thunderstorm-with-hail"}
                    if condition in extreme_conditions:
                        messages.append(f"⚠️ *Внимание! Экстремальная погода в {CITY_NAME}*\n{desc}\n🌡 Температура: {temp}°C\n💧 Влажность: {humidity}%\n🌬 Ветер: {wind} м/с\nБудьте осторожны!")

                if messages:
                    try:
                        for msg in messages:
                            await app.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
                    except Exception as e:
                        print(f"Ошибка при отправке уведомления пользователю {chat_id}: {e}")

        # Ждем 60 секунд до следующей проверки
        await asyncio.sleep(60)


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("menu", start))

    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, callback=text_message_handler))

    # Запускаем фоновую задачу после старта приложения
    async def on_startup(app):
        asyncio.create_task(notify_users(app))
    app.post_init = on_startup

    app.run_polling()

if __name__ == "__main__":
    main()