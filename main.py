import sqlite3
import os
from datetime import datetime
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
    
    if species.lower() in ['собака', 'пес', 'пёс']:
        if age < 1:
            base_per_kg = 40
        elif age < 7:
            base_per_kg = 30
        else:
            base_per_kg = 25
            
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
    
    if gender.lower() in ['самец', 'кот', 'пес']:
        base_per_kg *= 1.1
    else:
        base_per_kg *= 0.95
    
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

**Что умеет бот:**
• Добавлять питомцев (пошагово)
• Рассчитывать норму корма
• Вести календарь прививок
• Хранить все данные

📋 **Команды:**
/pets - Мои питомцы
/addpet - Добавить питомца
/vaccines - Прививки
/food - Питание
"""
    
    keyboard = [
        [KeyboardButton("🐕 Мои питомцы"), KeyboardButton("➕ Добавить питомца")],
        [KeyboardButton("💉 Прививки"), KeyboardButton("🍽️ Питание")]
    ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(menu_text, reply_markup=reply_markup)

async def start(update: Update, context: CallbackContext) -> None:
    await main_menu(update, context)

# ========== ПОШАГОВОЕ ДОБАВЛЕНИЕ ПИТОМЦА ==========

# Состояния для пошагового ввода
PET_NAME, PET_SPECIES, PET_BREED, PET_GENDER, PET_COLOR, PET_AGE, PET_WEIGHT, PET_HEIGHT, PET_BIRTHDAY, PET_ACTIVITY = range(10)

async def add_pet_start(update: Update, context: CallbackContext) -> None:
    """Начинаем пошаговое добавление питомца"""
    context.user_data['pet_step'] = PET_NAME
    await update.message.reply_text(
        "📝 **Добавление питомца** (шаг 1/10)\n\n"
        "Введите **кличку** питомца:"
    )

async def add_pet_process(update: Update, context: CallbackContext) -> None:
    """Обрабатываем каждый шаг ввода"""
    
    step = context.user_data.get('pet_step')
    
    if step is None:
        return
    
    text = update.message.text.strip()
    
    # Шаг 1: Имя
    if step == PET_NAME:
        context.user_data['pet_name'] = text
        context.user_data['pet_step'] = PET_SPECIES
        await update.message.reply_text(
            "✅ Кличка сохранена!\n\n"
            "📝 **Шаг 2/10**\n"
            "Введите **вид** животного (например: Собака, Кошка, Попугай):"
        )
    
    # Шаг 2: Вид
    elif step == PET_SPECIES:
        context.user_data['pet_species'] = text
        context.user_data['pet_step'] = PET_BREED
        await update.message.reply_text(
            "✅ Вид сохранен!\n\n"
            "📝 **Шаг 3/10**\n"
            "Введите **породу**:"
        )
    
    # Шаг 3: Порода
    elif step == PET_BREED:
        context.user_data['pet_breed'] = text
        context.user_data['pet_step'] = PET_GENDER
        await update.message.reply_text(
            "✅ Порода сохранена!\n\n"
            "📝 **Шаг 4/10**\n"
            "Введите **пол** (Кот/Кошка, Пес/Собака):"
        )
    
    # Шаг 4: Пол
    elif step == PET_GENDER:
        context.user_data['pet_gender'] = text
        context.user_data['pet_step'] = PET_COLOR
        await update.message.reply_text(
            "✅ Пол сохранен!\n\n"
            "📝 **Шаг 5/10**\n"
            "Введите **окрас**:"
        )
    
    # Шаг 5: Окрас
    elif step == PET_COLOR:
        context.user_data['pet_color'] = text
        context.user_data['pet_step'] = PET_AGE
        await update.message.reply_text(
            "✅ Окрас сохранен!\n\n"
            "📝 **Шаг 6/10**\n"
            "Введите **возраст** (в годах, только число):"
        )
    
    # Шаг 6: Возраст
    elif step == PET_AGE:
        try:
            age = int(text)
            context.user_data['pet_age'] = age
            context.user_data['pet_step'] = PET_WEIGHT
            await update.message.reply_text(
                "✅ Возраст сохранен!\n\n"
                "📝 **Шаг 7/10**\n"
                "Введите **вес** в кг (например: 4.5):"
            )
        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, введите число (возраст в годах)")
    
    # Шаг 7: Вес
    elif step == PET_WEIGHT:
        try:
            weight = float(text.replace(',', '.'))
            context.user_data['pet_weight'] = weight
            context.user_data['pet_step'] = PET_HEIGHT
            await update.message.reply_text(
                "✅ Вес сохранен!\n\n"
                "📝 **Шаг 8/10**\n"
                "Введите **рост** в см:"
            )
        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, введите число (вес в кг)")
    
    # Шаг 8: Рост
    elif step == PET_HEIGHT:
        try:
            height = float(text.replace(',', '.'))
            context.user_data['pet_height'] = height
            context.user_data['pet_step'] = PET_BIRTHDAY
            await update.message.reply_text(
                "✅ Рост сохранен!\n\n"
                "📝 **Шаг 9/10**\n"
                "Введите **дату рождения** в формате ДД.ММ.ГГГГ (например: 15.05.2020):"
            )
        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, введите число (рост в см)")
    
    # Шаг 9: День рождения
    elif step == PET_BIRTHDAY:
        try:
            # Проверяем формат даты
            datetime.strptime(text, '%d.%m.%Y')
            context.user_data['pet_birthday'] = text
            context.user_data['pet_step'] = PET_ACTIVITY
            await update.message.reply_text(
                "✅ Дата рождения сохранена!\n\n"
                "📝 **Шаг 10/10**\n"
                "Введите **уровень активности** (низкая/нормальная/высокая/очень высокая):"
            )
        except ValueError:
            await update.message.reply_text("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ")
    
    # Шаг 10: Активность и сохранение
    elif step == PET_ACTIVITY:
        activity = text.lower()
        if activity not in ['низкая', 'нормальная', 'высокая', 'очень высокая']:
            await update.message.reply_text("❌ Выберите из: низкая, нормальная, высокая, очень высокая")
            return
        
        context.user_data['pet_activity'] = text
        
        # Сохраняем в базу данных
        user_id = update.effective_user.id
        pet_name = context.user_data['pet_name']
        species = context.user_data['pet_species']
        breed = context.user_data['pet_breed']
        gender = context.user_data['pet_gender']
        color = context.user_data['pet_color']
        age = context.user_data['pet_age']
        weight = context.user_data['pet_weight']
        height = context.user_data['pet_height']
        birthday = context.user_data['pet_birthday']
        activity = context.user_data['pet_activity']
        
        cursor.execute('''
        INSERT INTO pets (user_id, pet_name, species, breed, gender, color, age, weight, height, birthday, activity_level)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, pet_name, species, breed, gender, color, age, weight, height, birthday, activity))
        
        pet_id = cursor.lastrowid
        
        # Рассчитываем норму корма
        daily_food = calculate_daily_food(weight, age, species, breed, gender, activity)
        
        cursor.execute('''
        INSERT INTO feeding (user_id, pet_id, daily_amount)
        VALUES (?, ?, ?)
        ''', (user_id, pet_id, daily_food))
        
        conn.commit()
        
        # Формируем красивый ответ
        response = f"""
✅ **ПИТОМЕЦ УСПЕШНО ДОБАВЛЕН!** 🎉

📋 **Карточка питомца:**
────────────────
🐾 **Кличка:** {pet_name}
🐕 **Вид:** {species}
🎖️ **Порода:** {breed}
👫 **Пол:** {gender}
🎨 **Окрас:** {color}
📅 **Возраст:** {age} лет
⚖️ **Вес:** {weight} кг
📏 **Рост:** {height} см
🎂 **День рождения:** {birthday}
🏃 **Активность:** {activity}
────────────────
🍽️ **Рекомендуемая норма корма:** {daily_food} г/день

🔍 Что дальше?
• Добавьте прививки через /vaccines
• Посмотрите всех питомцев через /pets
"""
        
        keyboard = [[KeyboardButton("🐕 Мои питомцы"), KeyboardButton("🔙 Назад")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(response, reply_markup=reply_markup)
        
        # Очищаем данные
        context.user_data.clear()

# ========== МОИ ПИТОМЦЫ ==========

async def show_pets(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    cursor.execute('SELECT * FROM pets WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
    pets = cursor.fetchall()
    
    if not pets:
        await update.message.reply_text(
            "🐾 У вас еще нет питомцев.\n"
            "Нажмите ➕ Добавить питомца чтобы создать первую карточку!"
        )
        return
    
    response = "📋 **ВАШИ ПИТОМЦЫ:**\n\n"
    
    for i, pet in enumerate(pets, 1):
        response += f"{i}. **{pet[2]}** ({pet[3]})\n"
        response += f"   🎖️ Порода: {pet[4]}\n"
        response += f"   👫 Пол: {pet[10]}\n"
        response += f"   📅 Возраст: {pet[6]} лет\n"
        response += f"   ⚖️ Вес: {pet[7]} кг\n"
        response += "────────────────\n"
    
    keyboard = [[KeyboardButton("➕ Добавить питомца"), KeyboardButton("🔙 Назад")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(response, reply_markup=reply_markup)

# ========== ПРИВИВКИ ==========

async def vaccines_menu(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    
    cursor.execute('SELECT id, pet_name FROM pets WHERE user_id = ?', (user_id,))
    pets = cursor.fetchall()
    
    if not pets:
        await update.message.reply_text("🐾 Сначала добавьте питомца через /addpet")
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
                try:
                    next_date_obj = datetime.strptime(next_date, '%Y-%m-%d').date()
                    status = "✅" if next_date_obj >= datetime.now().date() else "⚠️"
                    response += f"{status} {name}\n   📅 {date} → {next_date}\n"
                except:
                    response += f"📌 {name}\n   📅 {date} → {next_date}\n"
        else:
            response += f"🐕 **{pet_name}:** нет записей\n"
        response += "\n"
    
    response += "\n➕ Чтобы добавить прививку, используйте /addvaccine"
    
    await update.message.reply_text(response)

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
        await update.message.reply_text("🐾 Сначала добавьте питомца через /addpet")
        return
    
    response = "🍽️ **ПИТАНИЕ ПИТОМЦЕВ**\n\n"
    
    for pet in pets:
        name, weight, age, species, breed, gender, activity, amount = pet
        if not amount:
            amount = calculate_daily_food(weight, age, species, breed, gender, activity)
        
        response += f"🐕 **{name}**\n"
        response += f"   ⚖️ Вес: {weight} кг\n"
        response += f"   🍽️ Дневная норма: {amount} г\n\n"
    
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
    elif text == "🔙 Назад":
        await main_menu(update, context)
    elif context.user_data.get('pet_step') is not None:
        await add_pet_process(update, context)
    else:
        await main_menu(update, context)

# ========== ЗАПУСК БОТА ==========

def main() -> None:
    try:
        application = Application.builder().token(TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("pets", show_pets))
        application.add_handler(CommandHandler("addpet", add_pet_start))
        application.add_handler(CommandHandler("vaccines", vaccines_menu))
        application.add_handler(CommandHandler("food", food_menu))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))
        
        print("✅ Бот запущен и готов!")
        print("📝 Режим добавления: пошаговый ввод")
        application.run_polling()
        
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
