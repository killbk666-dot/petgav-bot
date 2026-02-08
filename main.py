import logging
import sqlite3
import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

# Настройка логов
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Создаем папку data, если ее нет
if not os.path.exists('data'):
    os.makedirs('data')

# Подключаем базу данных
conn = sqlite3.connect('data/pets.db', check_same_thread=False)
cursor = conn.cursor()

# Создаем таблицу для питомцев
cursor.execute('''
CREATE TABLE IF NOT EXISTS pets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    pet_name TEXT,
    species TEXT,
    breed TEXT,
    color TEXT,
    age INTEGER,
    weight REAL,
    height REAL,
    birthday TEXT
)
''')
conn.commit()

TOKEN = '8546883583:AAEMJZfwnPT-8dGilqd-chc7c5ZeY9TxN7Q'


# ===== КОМАНДЫ БОТА =====

# /start - начальная команда
async def start(update: Update, context: CallbackContext) -> None:
    keyboard = [[KeyboardButton("🐾 Животные")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "🐕 Добро пожаловать в PetGav! 🐈\n\n"
        "Храните данные о ваших питомцах здесь!\n\n"
        "Нажмите кнопку ниже или используйте команды:\n"
        "/addpet - Добавить питомца\n"
        "/mypets - Мои питомцы\n"
        "/help - Помощь",
        reply_markup=reply_markup
    )


# /help - помощь
async def help_command(update: Update, context: CallbackContext) -> None:
    help_text = """
📚 **Доступные команды:**
/start - Главное меню
/addpet - Добавить питомца
/mypets - Посмотреть питомцев
/help - Эта справка

📝 **Как добавить питомца:**
Используйте команду:
`/addpet Имя;Вид;Порода;Окрас;Возраст;Вес;Рост;ДеньРождения`

🐾 **Пример:**
`/addpet Барсик;Кошка;Британская;Серый;3;4.5;25;15.05.2020`
    """
    await update.message.reply_text(help_text)


# /addpet - добавить питомца
async def add_pet(update: Update, context: CallbackContext) -> None:
    if not context.args:
        await update.message.reply_text(
            "📝 **Добавление питомца**\n\n"
            "Введите данные в формате:\n"
            "`Имя;Вид;Порода;Окрас;Возраст;Вес;Рост;День рождения`\n\n"
            "📌 **Пример:**\n"
            "`/addpet Барсик;Кошка;Британская;Серый;3;4.5;25;15.05.2020`"
        )
        return

    # Объединяем все аргументы в одну строку
    data_text = ' '.join(context.args)
    parts = data_text.split(';')

    if len(parts) != 8:
        await update.message.reply_text(
            "❌ **Ошибка!** Нужно 8 параметров через точку с запятой!\n"
            "📋 Формат: Имя;Вид;Порода;Окрас;Возраст;Вес;Рост;День_рождения"
        )
        return

    try:
        # Извлекаем данные
        pet_name = parts[0].strip()
        species = parts[1].strip()
        breed = parts[2].strip()
        color = parts[3].strip()
        age = int(parts[4].strip())
        weight = float(parts[5].strip())
        height = float(parts[6].strip())
        birthday = parts[7].strip()

        # Сохраняем в базу данных
        cursor.execute('''
        INSERT INTO pets (user_id, pet_name, species, breed, color, age, weight, height, birthday)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            update.effective_user.id,
            pet_name,
            species,
            breed,
            color,
            age,
            weight,
            height,
            birthday
        ))
        conn.commit()

        # Показываем паспорт питомца
        response = f"""
✅ **Питомец добавлен!**

🐾 **ПАСПОРТ ПИТОМЦА:**
📛 Имя: {pet_name}
🏷️ Вид: {species}
🎖️ Порода: {breed}
🎨 Окрас: {color}
📅 Возраст: {age} лет
⚖️ Вес: {weight} кг
📏 Рост: {height} см
🎂 День рождения: {birthday}
        """

        await update.message.reply_text(response)

    except ValueError as e:
        await update.message.reply_text(
            "❌ **Ошибка в данных!**\n"
            "Убедитесь, что:\n"
            "• Возраст - целое число (например: 3)\n"
            "• Вес и рост - числа (например: 4.5 или 25)\n"
            "• Все поля заполнены правильно\n\n"
            "📌 Пример правильного ввода:\n"
            "`/addpet Барсик;Кошка;Британская;Серый;3;4.5;25;15.05.2020`"
        )


# /mypets - мои питомцы
async def my_pets(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id

    # Ищем питомцев пользователя
    cursor.execute('SELECT * FROM pets WHERE user_id = ?', (user_id,))
    pets = cursor.fetchall()

    if not pets:
        await update.message.reply_text("🐾 У вас пока нет питомцев. Добавьте первого командой /addpet")
        return

    # Формируем список
    response = "📋 **ВАШИ ПИТОМЦЫ:**\n\n"

    for pet in pets:
        response += f"🐕 **{pet[2]}** ({pet[3]})\n"
        response += f"   🎖️ Порода: {pet[4]}\n"
        response += f"   🎨 Окрас: {pet[5]}\n"
        response += f"   📅 Возраст: {pet[6]} лет\n"
        response += f"   ⚖️ Вес: {pet[7]} кг\n"
        response += f"   📏 Рост: {pet[8]} см\n"
        response += f"   🎂 День рождения: {pet[9]}\n"
        response += "─" * 30 + "\n"

    # Добавляем статистику
    cursor.execute('SELECT COUNT(*) FROM pets WHERE user_id = ?', (user_id,))
    count = cursor.fetchone()[0]

    response += f"\n📊 Всего питомцев: {count}"

    await update.message.reply_text(response)


# Обработчик кнопки "Животные"
async def animals_button(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [KeyboardButton("➕ Добавить питомца"), KeyboardButton("📋 Мои питомцы")],
        [KeyboardButton("❓ Помощь")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "🐾 **Меню животных**\n\n"
        "Выберите действие:",
        reply_markup=reply_markup
    )


# Обработчик текстовых сообщений (кнопок)
async def handle_text(update: Update, context: CallbackContext) -> None:
    text = update.message.text

    if text == "🐾 Животные":
        await animals_button(update, context)
    elif text == "➕ Добавить питомца":
        await update.message.reply_text(
            "📝 Чтобы добавить питомца, используйте команду:\n"
            "`/addpet Имя;Вид;Порода;Окрас;Возраст;Вес;Рост;День рождения`\n\n"
            "📌 Пример:\n"
            "`/addpet Барсик;Кошка;Британская;Серый;3;4.5;25;15.05.2020`"
        )
    elif text == "📋 Мои питомцы":
        await my_pets(update, context)
    elif text == "❓ Помощь":
        await help_command(update, context)
    else:
        await update.message.reply_text(
            "Я не понимаю эту команду. Используйте кнопки или команды.\n"
            "Введите /help для списка команд."
        )


# ===== ЗАПУСК БОТА =====

def main() -> None:
    """Запускаем бота"""
    print("🚀 Начинаю запуск бота PetGav...")

    # Создаем приложение
    application = Application.builder().token(TOKEN).build()

    # Регистрируем команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("addpet", add_pet))
    application.add_handler(CommandHandler("mypets", my_pets))

    # Регистрируем обработчик текста
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
