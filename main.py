import sqlite3
import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

print("=" * 50)
print("🚀 PetGav Bot запускается...")
print("=" * 50)

TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TOKEN:
    print("❌ ОШИБКА: TELEGRAM_TOKEN не найден!")
    exit(1)

print(f"✅ Токен получен: {TOKEN[:10]}...")

if not os.path.exists('data'):
    os.makedirs('data')

conn = sqlite3.connect('data/pets.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
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
)""")
conn.commit()

async def send_welcome(update: Update, context: CallbackContext) -> None:
    keyboard = [[KeyboardButton('🚀 Старт')]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text(
        "🐕🐈 Добро пожаловать в PetGav! 🐦🐢\n\n"
        "Ваш личный паспорт для питомцев!\n\n"
        "Нажмите кнопку **🚀 Старт** чтобы начать!",
        reply_markup=reply_markup
    )

async def start(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [KeyboardButton('🐾 Животные'), KeyboardButton('📋 Мои питомцы')],
        [KeyboardButton('➕ Добавить питомца'), KeyboardButton('❓ Помощь')]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "🚀 **PetGav - Паспорт для питомцев**\n\n"
        "Выберите действие:",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: CallbackContext) -> None:
    help_text = """
📚 **Команды:**
/start - Главное меню
/addpet - Добавить питомца
/mypets - Мои питомцы

📝 **Формат добавления:**
/addpet Имя;Вид;Порода;Окрас;Возраст;Вес;Рост;ДеньРождения

🐾 **Пример:**
/addpet Барсик;Кошка;Британская;Серый;3;4.5;25;15.05.2020
    """
    await update.message.reply_text(help_text)

async def add_pet(update: Update, context: CallbackContext) -> None:
    print(f"📝 Команда add_pet вызвана пользователем {update.effective_user.id}")
    print(f"📝 Аргументы: {context.args}")
    
    if not context.args:
        await update.message.reply_text(
            "📝 Введите:\n"
            "`/addpet Имя;Вид;Порода;Окрас;Возраст;Вес;Рост;День рождения`\n\n"
            "Пример:\n"
            "`/addpet Барсик;Кошка;Британская;Серый;3;4.5;25;15.05.2020`"
        )
        return
    
    data_text = ' '.join(context.args)
    parts = data_text.split(';')
    print(f"📝 Разделенные данные: {parts}")
    
    if len(parts) != 8:
        await update.message.reply_text("❌ Нужно 8 параметров через ;")
        return
    
    try:
        pet_name = parts[0].strip()
        species = parts[1].strip()
        breed = parts[2].strip()
        color = parts[3].strip()
        age = int(parts[4].strip())
        weight = float(parts[5].strip())
        height = float(parts[6].strip())
        birthday = parts[7].strip()
        
        print(f"📝 Сохранение в БД: {pet_name}, {species}, {breed}")
        
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
        print("✅ Данные сохранены в БД")
        
        response = f"✅ Питомец добавлен!\n\n🐾 {pet_name} ({species})\n🎖️ Порода: {breed}\n🎨 Окрас: {color}\n📅 Возраст: {age} лет\n⚖️ Вес: {weight} кг\n📏 Рост: {height} см\n🎂 День рождения: {birthday}"
        await update.message.reply_text(response)
        
    except ValueError as e:
        print(f"❌ Ошибка в данных: {e}")
        await update.message.reply_text("❌ Ошибка в данных! Проверьте числа.")

async def my_pets(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    print(f"📝 Поиск питомцев для пользователя {user_id}")
    
    cursor.execute('SELECT * FROM pets WHERE user_id = ?', (user_id,))
    pets = cursor.fetchall()
    print(f"📝 Найдено питомцев: {len(pets)}")
    
    if not pets:
        await update.message.reply_text("🐾 У вас нет питомцев")
        return
    
    response = "📋 Ваши питомцы:\n\n"
    for pet in pets:
        response += f"🐕 {pet[2]} ({pet[3]})\n   Порода: {pet[4]}, Окрас: {pet[5]}\n   Возраст: {pet[6]} лет, Вес: {pet[7]} кг\n────\n"
    
    await update.message.reply_text(response)

async def handle_text(update: Update, context: CallbackContext) -> None:
    text = update.message.text
    print(f"📝 Текст от пользователя: {text}")
    
    if text == "🚀 Старт":
        await start(update, context)
    
    elif text == "🐾 Животные":
        keyboard = [
            [KeyboardButton("➕ Добавить питомца"), KeyboardButton("📋 Мои питомцы")],
            [KeyboardButton("❓ Помощь"), KeyboardButton("🚀 Старт")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("🐾 Меню животных\n\nВыберите действие:", reply_markup=reply_markup)
    
    elif text == "📋 Мои питомцы":
        await my_pets(update, context)
    
    elif text == "➕ Добавить питомца":
        await update.message.reply_text(
            "Используйте команду:\n"
            "`/addpet Имя;Вид;Порода;Окрас;Возраст;Вес;Рост;День рождения`"
        )
    
    elif text == "❓ Помощь":
        await help_command(update, context)
    
    else:
        await send_welcome(update, context)

def main() -> None:
    try:
        print("🤖 Создание приложения...")
        application = Application.builder().token(TOKEN).build()
        
        print("📝 Регистрация команд...")
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("addpet", add_pet))
        application.add_handler(CommandHandler("mypets", my_pets))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        
        print("✅ Бот запущен и готов!")
        print("⚡ Ожидаю сообщения...")
        
        application.run_polling()
        
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
