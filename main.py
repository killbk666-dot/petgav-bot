import sqlite3
import os
import asyncio
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
    """
    Расчет дневной нормы корма в граммах
    """
    # Базовые нормы (грамм на кг веса в день)
    if species.lower() == 'собака':
        if age < 1:  # Щенок
            base_per_kg = 40
        elif age < 7:  # Взрослая
            base_per_kg = 30
        else:  # Пожилая
            base_per_kg = 25
            
        # Поправка на породу (крупные породы едят меньше на кг веса)
        breed_lower = breed.lower()
        if any(x in breed_lower for x in ['дог', 'мастиф', 'сенбернар', 'ньюфаундленд']):
            base_per_kg *= 0.8
        elif any(x in breed_lower for x in ['той', 'чихуахуа', 'йорк', 'шпиц']):  # Мелкие породы
            base_per_kg *= 1.2
            
    elif species.lower() == 'кошка':
        if age < 1:  # Котенок
            base_per_kg = 60
        elif age < 7:  # Взрослая
            base_per_kg = 50
        else:  # Пожилая
            base_per_kg = 45
    else:
        # Для других животных средняя норма
        base_per_kg = 40
    
    # Поправка на пол
    if gender.lower() == 'самец' or gender.lower() == 'кот':
        base_per_kg *= 1.1
    elif gender.lower() == 'самка' or gender.lower() == 'кошка':
        base_per_kg *= 0.95
    
    # Поправка на активность
    activity_multipliers = {
        'низкая': 0.8,
        'нормальная': 1.0,
        'высокая': 1.2,
        'очень высокая': 1.4
    }
    multiplier = activity_multipliers.get(activity_level.lower(), 1.0)
    
    daily_amount = weight * base_per_kg * multiplier
    
    # Округляем до 10 грамм
    return round(daily_amount / 10) * 10

# ========== СИСТЕМА НАПОМИНАНИЙ ==========

async def check_reminders(context: CallbackContext):
    """Проверяет и отправляет напоминания"""
    # Проверяем обычные напоминания
    cursor.execute('''
    SELECT id, user_id, reminder_text, reminder_date, reminder_time 
    FROM reminders 
    WHERE is_completed = 0 
    AND date(reminder_date) = date('now')
    AND time(reminder_time) <= time('now', '+1 minute')
    ''')
    
    reminders = cursor.fetchall()
    
    for reminder in reminders:
        reminder_id, user_id, text, date_str, time_str = reminder
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🔔 **НАПОМИНАНИЕ** 🔔\n\n{text}\n\n📅 {date_str} ⏰ {time_str}"
            )
            
            cursor.execute('UPDATE reminders SET is_completed = 1 WHERE id = ?', (reminder_id,))
            
        except Exception as e:
            print(f"❌ Ошибка отправки напоминания: {e}")
    
    # Проверяем просроченные прививки
    cursor.execute('''
    SELECT v.id, p.user_id, p.pet_name, v.vaccine_name, v.next_date
    FROM vaccinations v
    JOIN pets p ON v.pet_id = p.id
    WHERE date(v.next_date) < date('now')
    AND v.next_date NOT IN (
        SELECT vaccine_date FROM vaccinations 
        WHERE vaccine_name = v.vaccine_name 
        AND pet_id = v.pet_id 
        AND vaccine_date > v.next_date
    )
    ''')
    
    overdue_vaccines = cursor.fetchall()
    
    for vaccine in overdue_vaccines:
        vaccine_id, user_id, pet_name, vaccine_name, next_date = vaccine
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"⚠️ **ПРОСРОЧЕНА ПРИВИВКА** ⚠️\n\n"
                     f"Питомец: {pet_name}\n"
                     f"Прививка: {vaccine_name}\n"
                     f"Была назначена на: {next_date}\n\n"
                     f"Пожалуйста, запишитесь к ветеринару!"
            )
        except Exception as e:
            print(f"❌ Ошибка отправки напоминания о прививке: {e}")
    
    conn.commit()

# ========== КОМАНДЫ МЕНЮ ==========

async def main_menu(update: Update, context: CallbackContext) -> None:
    """Главное меню"""
    menu_text = """
🐾 **PetGav - Ваш личный помощник для питомцев**
────────────────────

**Полный контроль за здоровьем и уходом!**

📋 **Основные команды:**
/start - Главное меню
/pets - Мои питомцы
/addpet - Добавить питомца
/vaccines - Прививки
/food - Питание
/reminder - Напоминания
/help - Помощь

🎯 **Все данные в одном месте!**
────────────────────
*Забота в каждом уведомлении*
"""
    
    keyboard = [
        [KeyboardButton("🐕 Мои питомцы"), KeyboardButton("💉 Прививки")],
        [KeyboardButton("🍽️ Питание"), KeyboardButton("🔔 Напоминания")],
        [KeyboardButton("➕ Добавить питомца"), KeyboardButton("❓ Помощь")]
    ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(menu_text, reply_markup=reply_markup)

async def start(update: Update, context: CallbackContext) -> None:
    await main_menu(update, context)

# ========== МОИ ПИТОМЦЫ ==========

async def show_pets(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    cursor.execute('SELECT * FROM pets WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
    pets = cursor.fetchall()
    
    if not pets:
        keyboard = [[KeyboardButton("➕ Добавить питомца")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "🐾 У вас еще нет питомцев. Добавьте первого!",
            reply_markup=reply_markup
        )
        return
    
    response = "📋 **ВАШИ ПИТОМЦЫ:**\n\n"
    
    for i, pet in enumerate(pets, 1):
        response += f"{i}. **{pet[2]}** ({pet[3]})\n"
        response += f"   🎖️ Порода: {pet[4]}\n"
        response += f"   👫 Пол: {pet[10] if pet[10] else 'Не указан'}\n"
        response += f"   📅 Возраст: {pet[6]} лет\n"
        response += f"   ⚖️ Вес: {pet[7]} кг\n"
        response += "────────────────────\n"
    
    keyboard = [
        [KeyboardButton("💉 Прививки"), KeyboardButton("🍽️ Питание")],
        [KeyboardButton("➕ Добавить питомца"), KeyboardButton("🔙 Назад")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(response, reply_markup=reply_markup)

# ========== ДОБАВИТЬ ПИТОМЦА ==========

async def add_pet_start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "📝 **Добавление питомца**\n\n"
        "Введите данные в формате:\n"
        "`Имя;Вид;Порода;Пол;Окрас;Возраст;Вес;Рост;День рождения;Уровень активности`\n\n"
        "📌 **Примеры:**\n"
        "`Барсик;Кошка;Британская;Кот;Серый;3;4.5;25;15.05.2020;Нормальная`\n"
        "`Рекс;Собака;Лабрадор;Пес;Палевый;2;30;55;10.06.2021;Высокая`\n\n"
        "📊 **Уровни активности:**\n"
        "• Низкая (пожилые, мало двигаются)\n"
        "• Нормальная (обычные прогулки)\n"
        "• Высокая (активные игры, тренировки)\n"
        "• Очень высокая (рабочие собаки, спорт)\n\n"
        "Отправьте данные одним сообщением:"
    )
    context.user_data['awaiting_pet_data'] = True

async def add_pet_process(update: Update, context: CallbackContext) -> None:
    if not context.user_data.get('awaiting_pet_data'):
        return
    
    data_text = update.message.text.strip()
    parts = data_text.split(';')
    
    if len(parts) != 10:
        await update.message.reply_text("❌ Нужно 10 параметров через ';'. Попробуйте снова.")
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
        ''', (
            update.effective_user.id,
            pet_name,
            species,
            breed,
            gender,
            color,
            age,
            weight,
            height,
            birthday,
            activity
        ))
        pet_id = cursor.lastrowid
        
        # Автоматически рассчитываем норму корма
        daily_food = calculate_daily_food(weight, age, species, breed, gender, activity)
        
        cursor.execute('''
        INSERT INTO feeding (user_id, pet_id, food_type, daily_amount)
        VALUES (?, ?, ?, ?)
        ''', (
            update.effective_user.id,
            pet_id,
            'Сухой корм',
            daily_food
        ))
        
        conn.commit()
        
        response = f"""
✅ **Питомец добавлен!**

🐾 **{pet_name}** ({species})
👫 Пол: {gender}
🎖️ Порода: {breed}
🎨 Окрас: {color}
📅 Возраст: {age} лет
⚖️ Вес: {weight} кг
📏 Рост: {height} см
🎂 День рождения: {birthday}
🏃 Уровень активности: {activity}

🍽️ **Рекомендуемая дневная норма:** {daily_food} г сухого корма
"""
        
        keyboard = [
            [KeyboardButton("💉 Добавить прививку"), KeyboardButton("🍽️ Настроить питание")],
            [KeyboardButton("🔙 Назад")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(response, reply_markup=reply_markup)
        
    except ValueError:
        await update.message.reply_text("❌ Ошибка в данных! Проверьте числа и формат.")
    
    context.user_data['awaiting_pet_data'] = False

# ========== ПРИВИВКИ ==========

async def vaccines_menu(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    
    # Получаем питомцев пользователя
    cursor.execute('SELECT id, pet_name FROM pets WHERE user_id = ?', (user_id,))
    pets = cursor.fetchall()
    
    if not pets:
        await update.message.reply_text("🐾 Сначала добавьте питомца!")
        return
    
    # Формируем список прививок для всех питомцев
    response = "💉 **КАЛЕНДАРЬ ПРИВИВОК**\n\n"
    
    all_vaccines = []
    for pet_id, pet_name in pets:
        cursor.execute('''
        SELECT vaccine_name, vaccine_date, next_date, notes 
        FROM vaccinations 
        WHERE user_id = ? AND pet_id = ?
        ORDER BY next_date
        ''', (user_id, pet_id))
        
        vaccines = cursor.fetchall()
        
        if vaccines:
            response += f"🐕 **{pet_name}:**\n"
            for i, (name, date, next_date, notes) in enumerate(vaccines, 1):
                status = "✅" if datetime.strptime(next_date, '%Y-%m-%d').date() >= datetime.now().date() else "⚠️"
                response += f"{i}. {status} {name}\n"
                response += f"   📅 Последняя: {date}\n"
                response += f"   📅 Следующая: {next_date}\n"
                if notes:
                    response += f"   📝 Заметки: {notes}\n"
                response += "\n"
            response += "────────────────────\n"
            
            all_vaccines.extend([(pet_id, pet_name, v) for v in vaccines])
    
    if not all_vaccines:
        response = "💉 **КАЛЕНДАРЬ ПРИВИВОК**\n\n"
        response += "У ваших питомцев еще нет записей о прививках.\n\n"
        response += "**Основные прививки для животных:**\n"
        response += "• Комплексная (ежегодно)\n"
        response += "• Бешенство (ежегодно)\n"
        response += "• Лептоспироз (ежегодно)\n"
        response += "• Парагрипп (по рекомендации)\n\n"
        response += "📅 **Добавьте первую прививку!**"
    
    keyboard = [
        [KeyboardButton("➕ Добавить прививку"), KeyboardButton("📅 Ближайшие")],
        [KeyboardButton("⚠️ Просроченные"), KeyboardButton("🔙 Назад")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(response, reply_markup=reply_markup)

async def add_vaccine_start(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    cursor.execute('SELECT id, pet_name FROM pets WHERE user_id = ?', (user_id,))
    pets = cursor.fetchall()
    
    if not pets:
        await update.message.reply_text("🐾 Сначала добавьте питомца!")
        return
    
    # Сохраняем список питомцев в контексте
    context.user_data['pets_list'] = pets
    
    # Показываем список питомцев для выбора
    pets_text = "📋 **Выберите питомца:**\n\n"
    for i, (pet_id, pet_name) in enumerate(pets, 1):
        pets_text += f"{i}. {pet_name}\n"
    
    pets_text += "\nОтправьте номер питомца:"
    
    await update.message.reply_text(pets_text)
    context.user_data['awaiting_pet_choice'] = True

async def add_vaccine_process(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    
    if context.user_data.get('awaiting_pet_choice'):
        try:
            pet_num = int(update.message.text.strip()) - 1
            pets = context.user_data.get('pets_list', [])
            
            if 0 <= pet_num < len(pets):
                pet_id, pet_name = pets[pet_num]
                context.user_data['selected_pet_id'] = pet_id
                context.user_data['selected_pet_name'] = pet_name
                
                await update.message.reply_text(
                    f"📝 **Добавление прививки для {pet_name}**\n\n"
                    "Введите данные в формате:\n"
                    "`Название прививки;Дата прививки;Дата следующей;Заметки`\n\n"
                    "📌 **Пример:**\n"
                    "`Комплексная вакцина;15.02.2024;15.02.2025;Все хорошо, без реакций`\n"
                    "`Вакцина от бешенства;10.01.2024;10.01.2025;`\n\n"
                    "Отправьте данные:"
                )
                context.user_data['awaiting_pet_choice'] = False
                context.user_data['awaiting_vaccine_data'] = True
            else:
                await update.message.reply_text("❌ Неверный номер. Попробуйте снова.")
                
        except ValueError:
            await update.message.reply_text("❌ Введите номер цифрой.")
    
    elif context.user_data.get('awaiting_vaccine_data'):
        try:
            data_text = update.message.text.strip()
            parts = data_text.split(';')
            
            if len(parts) < 3:
                await update.message.reply_text("❌ Нужно минимум 3 параметра. Попробуйте снова.")
                return
            
            vaccine_name = parts[0].strip()
            vaccine_date = datetime.strptime(parts[1].strip(), '%d.%m.%Y').date()
            next_date = datetime.strptime(parts[2].strip(), '%d.%m.%Y').date()
            notes = parts[3].strip() if len(parts) > 3 else ""
            
            pet_id = context.user_data.get('selected_pet_id')
            pet_name = context.user_data.get('selected_pet_name', 'Питомец')
            
            cursor.execute('''
            INSERT INTO vaccinations (user_id, pet_id, vaccine_name, vaccine_date, next_date, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                pet_id,
                vaccine_name,
                vaccine_date.strftime('%Y-%m-%d'),
                next_date.strftime('%Y-%m-%d'),
                notes
            ))
            conn.commit()
            
            # Создаем напоминание за неделю до следующей прививки
            reminder_date = next_date - timedelta(days=7)
            cursor.execute('''
            INSERT INTO reminders (user_id, reminder_text, reminder_date, reminder_time)
            VALUES (?, ?, ?, ?)
            ''', (
                user_id,
                f"Напоминание о прививке для {pet_name}: {vaccine_name}",
                reminder_date.strftime('%Y-%m-%d'),
                '10:00'
            ))
            conn.commit()
            
            response = f"""
✅ **Прививка добавлена!**

🐕 Питомец: {pet_name}
💉 Прививка: {vaccine_name}
📅 Дата: {vaccine_date.strftime('%d.%m.%Y')}
📅 Следующая: {next_date.strftime('%d.%m.%Y')}
📝 Заметки: {notes if notes else 'Нет'}

🔔 Напоминание будет отправлено за неделю до следующей прививки!
"""
            
            keyboard = [[KeyboardButton("💉 Календарь прививок"), KeyboardButton("🔙 Назад")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(response, reply_markup=reply_markup)
            
        except ValueError as e:
            await update.message.reply_text(f"❌ Ошибка в данных: {e}\nПроверьте формат даты (ДД.ММ.ГГГГ)")
        
        context.user_data['awaiting_vaccine_data'] = False
        context.user_data.pop('selected_pet_id', None)
        context.user_data.pop('selected_pet_name', None)

# ========== ПИТАНИЕ ==========

async def food_menu(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    
    # Получаем питомцев с информацией о кормлении
    cursor.execute('''
    SELECT p.id, p.pet_name, p.species, p.weight, p.age, p.breed, p.gender, p.activity_level,
           f.daily_amount, f.food_type, f.feeding_times
    FROM pets p
    LEFT JOIN feeding f ON p.id = f.pet_id AND f.user_id = p.user_id
    WHERE p.user_id = ?
    ''', (user_id,))
    
    pets = cursor.fetchall()
    
    if not pets:
        await update.message.reply_text("🐾 Сначала добавьте питомца!")
        return
    
    response = "🍽️ **РЕЖИМ ПИТАНИЯ**\n\n"
    
    for pet in pets:
        pet_id, pet_name, species, weight, age, breed, gender, activity, daily_amount, food_type, feeding_times = pet
        
        # Если нет записи о кормлении, рассчитываем
        if not daily_amount:
            daily_amount = calculate_daily_food(weight, age, species, breed, gender, activity)
            food_type = 'Сухой корм (рекомендация)'
            feeding_times = '2-3 раза в день'
        
        response += f"🐕 **{pet_name}** ({species})\n"
        response += f"   ⚖️ Вес: {weight} кг\n"
        response += f"   🍽️ Дневная норма: {daily_amount} г\n"
        response += f"   🥫 Тип корма: {food_type}\n"
        response += f"   ⏰ Режим: {feeding_tings_times if feeding_times else 'Не настроен'}\n"
        
        # Рекомендации по кормлению
        if species.lower() == 'собака':
            response += f"   💡 Совет: {round(daily_amount/2)} г утром, {round(daily_amount/2)} г вечером\n"
        elif species.lower() == 'кошка':
            response += f"   💡 Совет: {round(daily_amount/3)} г 3 раза в день\n"
        
        response += "\n"
    
    response += "📊 **Общие рекомендации:**\n"
    response += "• Следите за весом питомца\n"
    response += "• Регулярно обновляйте воду\n"
    response += "• Консультируйтесь с ветеринаром\n"
    
    keyboard = [
        [KeyboardButton("📊 Пересчитать нормы"), KeyboardButton("⏰ Настроить время")],
        [KeyboardButton("🍖 Изменить тип корма"), KeyboardButton("🔙 Назад")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(response, reply_markup=reply_markup)

async def recalculate_food(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    
    cursor.execute('SELECT id, pet_name, weight, age, species, breed, gender, activity_level FROM pets WHERE user_id = ?', (user_id,))
    pets = cursor.fetchall()
    
    if not pets:
        await update.message.reply_text("🐾 Нет питомцев для пересчета.")
        return
    
    updated = 0
    response = "📊 **ОБНОВЛЕННЫЕ НОРМЫ КОРМА:**\n\n"
    
    for pet in pets:
        pet_id, pet_name, weight, age, species, breed, gender, activity = pet
        
        # Рассчитываем новую норму
        new_amount = calculate_daily_food(weight, age, species, breed, gender, activity)
        
        # Обновляем в базе
        cursor.execute('''
        INSERT OR REPLACE INTO feeding (user_id, pet_id, daily_amount, last_updated)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, pet_id, new_amount))
        
        response += f"🐕 {pet_name}: {new_amount} г/день\n"
        updated += 1
    
    conn.commit()
    
    response += f"\n✅ Обновлено норм: {updated}"
    
    await update.message.reply_text(response)

# ========== НАПОМИНАНИЯ ==========

async def create_reminder_start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "🔔 **Создание напоминания**\n\n"
        "Введите данные в формате:\n"
        "`Текст напоминания;Дата;Время`\n\n"
        "📌 **Примеры:**\n"
        "`Отвести кота к ветеринару;15.02.2024;14:30`\n"
        "`Купить корм для собаки;завтра;10:00`\n"
        "`Сделать прививку;сегодня;18:00`\n\n"
        "Отправьте данные одним сообщением:"
    )
    context.user_data['awaiting_reminder'] = True

async def create_reminder_process(update: Update, context: CallbackContext) -> None:
    if not context.user_data.get('awaiting_reminder'):
        return
    
    data_text = update.message.text.strip()
    parts = data_text.split(';')
    
    if len(parts) != 3:
        await update.message.reply_text("❌ Нужно 3 параметра через ';'. Попробуйте снова.")
        return
    
    try:
        text = parts[0].strip()
        date_str = parts[1].strip().lower()
        time_str = parts[2].strip()
        
        # Обработка специальных значений даты
        today = datetime.now().date()
        if date_str == 'сегодня':
            date = today
        elif date_str == 'завтра':
            date = today + timedelta(days=1)
        else:
            # Парсим дату в формате ДД.ММ.ГГГГ
            try:
                date = datetime.strptime(date_str, '%d.%m.%Y').date()
            except:
                date = datetime.strptime(date_str, '%d.%m.%y').date()
        
        # Парсим время
        try:
            time = datetime.strptime(time_str, '%H:%M').time()
        except:
            await update.message.reply_text("❌ Неверный формат времени. Используйте ЧЧ:ММ")
            return
        
        # Проверяем что напоминание в будущем
        reminder_datetime = datetime.combine(date, time)
        if reminder_datetime < datetime.now():
            await update.message.reply_text("❌ Нельзя создать напоминание в прошлом!")
            return
        
        cursor.execute('''
        INSERT INTO reminders (user_id, reminder_text, reminder_date, reminder_time)
        VALUES (?, ?, ?, ?)
        ''', (
            update.effective_user.id,
            text,
            date.strftime('%Y-%m-%d'),
            time.strftime('%H:%M')
        ))
        conn.commit()
        
        response = f"""
✅ **Напоминание создано!**

📝 Текст: {text}
📅 Дата: {date.strftime('%d.%m.%Y')}
⏰ Время: {time.strftime('%H:%M')}

Я напомню вам в назначенное время!
"""
        
        await update.message.reply_text(response)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}\nПопробуйте снова.")
    
    context.user_data['awaiting_reminder'] = False

async def show_reminders(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    
    cursor.execute('''
    SELECT id, reminder_text, reminder_date, reminder_time, is_completed 
    FROM reminders 
    WHERE user_id = ? 
    ORDER BY reminder_date, reminder_time
    ''', (user_id,))
    
    reminders = cursor.fetchall()
    
    if not reminders:
        await update.message.reply_text("📅 У вас нет активных напоминаний.")
        return
    
    active = []
    completed = []
    
    for reminder in reminders:
        if reminder[4]:  # is_completed
            completed.append(reminder)
        else:
            active.append(reminder)
    
    response = "🔔 **ВАШИ НАПОМИНАНИЯ**\n\n"
    
    if active:
        response += "📋 **АКТИВНЫЕ:**\n"
        for rem in active:
            date_obj = datetime.strptime(rem[2], '%Y-%m-%d')
            response += f"• {rem[1]}\n  📅 {date_obj.strftime('%d.%m.%Y')} ⏰ {rem[3]}\n\n"
    
    if completed:
        response += "✅ **ВЫПОЛНЕННЫЕ:**\n"
        for rem in completed:
            date_obj = datetime.strptime(rem[2], '%Y-%m-%d')
            response += f"• {rem[1]}\n  📅 {date_obj.strftime('%d.%m.%Y')} ⏰ {rem[3]}\n\n"
    
    await update.message.reply_text(response)

# ========== ПОМОЩЬ ==========

async def help_command(update: Update, context: CallbackContext) -> None:
    help_text = """
📚 **КОМАНДЫ БОТА:**

**Основное меню:**
/start - Главное меню
/pets - Мои питомцы
/addpet - Добавить питомца
/vaccines - Календарь прививок
/food - Режим питания
/reminder - Создать напоминание
/myreminders - Мои напоминания
/help - Эта справка

**Добавление питомца:**
Формат: `Имя;Вид;Порода;Пол;Окрас;Возраст;Вес;Рост;День рождения;Активность`
Пример: `Барсик;Кошка;Британская;Кот;Серый;3;4.5;25;15.05.2020;Нормальная`

**Прививки:**
Формат: `Название;Дата;Следующая дата;Заметки`
Пример: `Комплексная вакцина;15.02.2024;15.02.2025;Все хорошо`

**Питание:**
Бот автоматически рассчитывает дневную норму корма
на основе веса, возраста, породы и активности

**Напоминания:**
Формат: `Текст;Дата;Время`
Пример: `Купить корм;завтра;10:00`

📞 **Поддержка:** @PetGavBot
"""
    
    await update.message.reply_text(help_text)

# ========== ОБРАБОТЧИК КНОПОК ==========

async def handle_buttons(update: Update, context: CallbackContext) -> None:
    text = update.message.text
    
    if text == "🔙 Назад" or text == "🔄 Перезапустить бота":
        await main_menu(update, context)
    
    elif text == "🐕 Мои питомцы":
        await show_pets(update, context)
    
    elif text == "➕ Добавить питомца":
        await add_pet_start(update, context)
    
    elif text == "💉 Прививки" or text == "💉 Календарь прививок":
        await vaccines_menu(update, context)
    
    elif text == "➕ Добавить прививку":
        await add_vaccine_start(update, context)
    
    elif text == "🍽️ Питание":
        await food_menu(update, context)
    
    elif text == "📊 Пересчитать нормы":
        await recalculate_food(update, context)
    
    elif text == "🔔 Напоминания":
        await create_reminder_start(update, context)
    
    elif text == "📅 Мои напоминания":
        await show_reminders(update, context)
    
    elif text == "❓ Помощь":
        await help_command(update, context)
    
    # Обработка ввода данных
    elif context.user_data.get('awaiting_pet_data'):
        await add_pet_process(
