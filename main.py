import sqlite3
import os
from datetime import datetime, timedelta
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

# ИИ функции ОТКЛЮЧЕНЫ для стабильной работы
AI_ENABLED = False
print("⚠️ ИИ функции отключены (для стабильной работы)")

if not os.path.exists('data'):
    os.makedirs('data')

# Подключаем базы данных
conn = sqlite3.connect('data/pets.db', check_same_thread=False)
cursor = conn.cursor()

# Таблица для питомцев
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
    birthday TEXT,
    gender TEXT,
    activity_level TEXT DEFAULT 'normal',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""")

# Таблица для прививок
cursor.execute("""
CREATE TABLE IF NOT EXISTS vaccinations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    pet_id INTEGER,
    vaccine_name TEXT,
    vaccine_date DATE,
    next_date DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""")

# Таблица для напоминаний
cursor.execute("""
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    reminder_text TEXT,
    reminder_date DATE,
    reminder_time TIME,
    is_completed BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""")

# Таблица для кормления
cursor.execute("""
CREATE TABLE IF NOT EXISTS feeding (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    pet_id INTEGER,
    food_type TEXT,
    daily_amount REAL,
    feeding_times TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""")
conn.commit()

# ========== РАСЧЕТ НОРМЫ КОРМА ==========

def calculate_daily_food(weight, age, species, breed, gender, activity_level='normal'):
    """Расчет дневной нормы корма в граммах"""
    
    # Базовые нормы (грамм на кг веса в день)
    if species.lower() in ['собака', 'пес', 'пёс']:
        if age < 1:  # Щенок
            base_per_kg = 40
        elif age < 7:  # Взрослая
            base_per_kg = 30
        else:  # Пожилая
            base_per_kg = 25
            
        # Поправка на породу
        breed_lower = breed.lower()
        if any(x in breed_lower for x in ['дог', 'мастиф', 'сенбернар', 'ньюфаундленд']):
            base_per_kg *= 0.8
        elif any(x in breed_lower for x in ['той', 'чихуахуа', 'йорк', 'шпиц']):
            base_per_kg *= 1.2
            
    elif species.lower() in ['кошка', 'кот']:
        if age < 1:
            base_per_kg = 60
        elif age < 7:
            base_per_kg = 50
        else:
            base_per_kg = 45
    else:
        base_per_kg = 40
    
    # Поправка на пол
    if gender.lower() in ['самец', 'кот', 'пес']:
        base_per_kg *= 1.1
    else:
        base_per_kg *= 0.95
    
    # Поправка на активность
    activity_multipliers = {
        'низкая': 0.8, 'низкий': 0.8,
        'нормальная': 1.0, 'нормальный': 1.0,
        'средняя': 1.0, 'средний': 1.0,
        'высокая': 1.2, 'высокий': 1.2,
        'очень высокая': 1.4, 'очень высокий': 1.4,
    }
    multiplier = activity_multipliers.get(activity_level.lower(), 1.0)
    
    daily_amount = weight * base_per_kg * multiplier
    return round(daily_amount / 10) * 10

# ========== КОМАНДЫ МЕНЮ ==========

async def main_menu(update: Update, context: CallbackContext) -> None:
    """Главное меню"""
    menu_text = """
🐾 **PetGav - Ваш помощник для питомцев**
────────────────────

**Полный контроль за здоровьем и уходом!**

📋 **Основные команды:**
/pets - Мои питомцы
/addpet - Добавить питомца
/vaccines - Прививки
/food - Питание
/help - Помощь

🎯 **Все данные в одном месте!**
"""
    
    keyboard = [
        [KeyboardButton("🐕 Мои питомцы"), KeyboardButton("💉 Прививки")],
        [KeyboardButton("🍽️ Питание"), KeyboardButton("➕ Добавить питомца")],
        [KeyboardButton("❓ Помощь")]
    ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(menu_text, reply_markup=reply_markup)

async def start(update: Update, context: CallbackContext) -> None:
    await main_menu(update, context)

async def help_command(update: Update, context: CallbackContext) -> None:
    help_text = """
📚 **КОМАНДЫ БОТА:**

/pets - Мои питомцы
/addpet - Добавить питомца
/vaccines - Календарь прививок
/food - Режим питания

**Добавление питомца:**
`Имя;Вид;Порода;Пол;Окрас;Возраст;Вес;Рост;ДД.ММ.ГГГГ;Активность`

**Прививки:**
`Название;ДД.ММ.ГГГГ;ДД.ММ.ГГГГ;Заметки`
"""
    await update.message.reply_text(help_text)

# ========== МОИ ПИТОМЦЫ ==========

async def show_pets(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    cursor.execute('SELECT * FROM pets WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
    pets = cursor.fetchall()
    
    if not pets:
        await update.message.reply_text("🐾 У вас еще нет питомцев. Добавьте через /addpet")
        return
    
    response = "📋 **ВАШИ ПИТОМЦЫ:**\n\n"
    for i, pet in enumerate(pets, 1):
        response += f"{i}. **{pet[2]}** ({pet[3]})\n"
        response += f"   🎖️ Порода: {pet[4]}\n"
        response += f"   👫 Пол: {pet[10]}\n"
        response += f"   📅 Возраст: {pet[6]} лет\n"
        response += f"   ⚖️ Вес: {pet[7]} кг\n\n"
    
    await update.message.reply_text(response)

# ========== ДОБАВИТЬ ПИТОМЦА ==========

async def add_pet_start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "📝 **Добавление питомца**\n\n"
        "Введите данные в формате:\n"
        "`Имя;Вид;Порода;Пол;Окрас;Возраст;Вес;Рост;ДД.ММ.ГГГГ;Активность`\n\n"
        "📌 **Пример:**\n"
        "`Барсик;Кошка;Британская;Кот;Серый;3;4.5;25;15.05.2020;Нормальная`\n\n"
        "Активность: низкая, нормальная, высокая, очень высокая"
    )
    context.user_data['awaiting_pet_data'] = True

async def add_pet_process(update: Update, context: CallbackContext) -> None:
    if not context.user_data.get('awaiting_pet_data'):
        return
    
    data_text = update.message.text.strip()
    parts = data_text.split(';')
    
    if len(parts) != 10:
        await update.message.reply_text("❌ Нужно 10 параметров через ';'")
        return
    
    try:
        pet_name = parts[0].strip()
        species = parts[1].strip()
        breed = parts[2].strip()
        gender = parts[3].strip()
        color = parts[4].strip()
        age = int(parts[5].strip())
        weight = float(parts[6].strip())
        height = float(parts[7].strip())
        birthday = parts[8].strip()
        activity = parts[9].strip()
        
        cursor.execute('''
        INSERT INTO pets (user_id, pet_name, species, breed, gender, color, age, weight, height, birthday, activity_level)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (update.effective_user.id, pet_name, species, breed, gender, color, age, weight, height, birthday, activity))
        
        pet_id = cursor.lastrowid
        daily_food = calculate_daily_food(weight, age, species, breed, gender, activity)
        
        cursor.execute('''
        INSERT INTO feeding (user_id, pet_id, daily_amount)
        VALUES (?, ?, ?)
        ''', (update.effective_user.id, pet_id, daily_food))
        
        conn.commit()
        
        response = f"""
✅ **Питомец добавлен!**

🐾 {pet_name} ({species})
👫 Пол: {gender}
🎖️ Порода: {breed}
🎨 Окрас: {color}
📅 Возраст: {age} лет
⚖️ Вес: {weight} кг
📏 Рост: {height} см

🍽️ **Дневная норма:** {daily_food} г
"""
        await update.message.reply_text(response)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
    
    context.user_data['awaiting_pet_data'] = False

# ========== ПИТАНИЕ ==========

async def food_menu(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    
    cursor.execute('''
    SELECT p.pet_name, p.weight, p.age, p.species, p.breed, p.gender, p.activity_level, f.daily_amount
    FROM pets p
    LEFT JOIN feeding f ON p.id = f.pet_id
    WHERE p.user_id = ?
    ''', (user_id,))
    
    pets = cursor.fetchall()
    
    if not pets:
        await update.message.reply_text("🐾 Сначала добавьте питомца!")
        return
    
    response = "🍽️ **ПИТАНИЕ ПИТОМЦЕВ**\n\n"
    for pet in pets:
        name, weight, age, species, breed, gender, activity, amount = pet
        if not amount:
            amount = calculate_daily_food(weight, age, species, breed, gender, activity)
        
        response += f"🐕 **{name}**\n"
        response += f"   ⚖️ Вес: {weight} кг\n"
        response += f"   🍽️ Норма: {amount} г/день\n\n"
    
    await update.message.reply_text(response)

# ========== ПРИВИВКИ ==========

async def vaccines_menu(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    
    cursor.execute('SELECT id, pet_name FROM pets WHERE user_id = ?', (user_id,))
    pets = cursor.fetchall()
    
    if not pets:
        await update.message.reply_text("🐾 Сначала добавьте питомца!")
        return
    
    response = "💉 **ПРИВИВКИ**\n\n"
    for pet_id, pet_name in pets:
        cursor.execute('''
        SELECT vaccine_name, vaccine_date, next_date 
        FROM vaccinations 
        WHERE user_id = ? AND pet_id = ?
        ORDER BY next_date
        ''', (user_id, pet_id))
        
        vaccines = cursor.fetchall()
        if vaccines:
            response += f"🐕 **{pet_name}:**\n"
            for name, date, next_date in vaccines:
                status = "✅" if datetime.strptime(next_date, '%Y-%m-%d').date() >= datetime.now().date() else "⚠️"
                response += f"{status} {name}\n   📅 {date} → {next_date}\n"
        else:
            response += f"🐕 **{pet_name}:** нет записей\n"
    
    await update.message.reply_text(response)

# ========== ОБРАБОТЧИК КНОПОК ==========

async def handle_buttons(update: Update, context: CallbackContext) -> None:
    text = update.message.text
    
    if text == "🐕 Мои питомцы":
        await show_pets(update, context)
    elif text == "➕ Добавить питомца":
        await add_pet_start(update, context)
    elif text == "💉 Прививки":
        await vaccines_menu(update, context)
    elif text == "🍽️ Питание":
        await food_menu(update, context)
    elif text == "❓ Помощь":
        await help_command(update, context)
    elif text == "🔙 Назад" or text == "/start":
        await main_menu(update, context)
    elif context.user_data.get('awaiting_pet_data'):
        await add_pet_process(update, context)
    else:
        await main_menu(update, context)

# ========== ЗАПУСК БОТА ==========

def main() -> None:
    try:
        application = Application.builder().token(TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("pets", show_pets))
        application.add_handler(CommandHandler("addpet", add_pet_start))
        application.add_handler(CommandHandler("food", food_menu))
        application.add_handler(CommandHandler("vaccines", vaccines_menu))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))
        
        print("✅ Бот запущен и готов!")
        application.run_polling()
        
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")

if __name__ == '__main__':
    main()
