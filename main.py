import asyncio
import json
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from config import ADMIN_IDS, BOT_TOKEN


# Пример данных - замените на вашу таблицу
# Структура: класс, полугодие, предмет, информация
schedule_data = [
    {"класс": "9А", "полугодие": "1", "предмет": "Математика",
     "информация": "Учебник: Алгебра 9 класс\nУчитель: Иванов И.И.\nКабинет: 205"},
]


# Состояния FSM
class ScheduleStates(StatesGroup):
    choosing_class = State()
    choosing_semester = State()
    choosing_subject = State()


# Состояния для админки
class AdminStates(StatesGroup):
    adding_class = State()
    adding_semester = State()
    adding_subject = State()
    adding_info = State()
    adding_admin_id = State()
    deleting_record = State()
    editing_select_record = State()
    editing_field = State()
    editing_value = State()


# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# Функции для работы с данными
def save_data():
    """Сохранить данные в файл"""
    try:
        with open('schedule_data.json', 'w', encoding='utf-8') as f:
            json.dump(schedule_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения данных: {e}")


def load_data():
    """Загрузить данные из файла"""
    global schedule_data
    try:
        with open('schedule_data.json', 'r', encoding='utf-8') as f:
            schedule_data = json.load(f)
    except FileNotFoundError:
        save_data()  # Создать файл с начальными данными
    except Exception as e:
        print(f"Ошибка загрузки данных: {e}")


def is_admin(user_id: int) -> bool:
    """Проверить, является ли пользователь администратором"""
    return user_id in ADMIN_IDS


# Функции для получения уникальных значений из данных
def get_unique_classes():
    """Получить список уникальных классов"""
    return sorted(list(set(item["класс"] for item in schedule_data)))


def get_unique_semesters(class_name):
    """Получить список полугодий для выбранного класса"""
    semesters = [item["полугодие"] for item in schedule_data if item["класс"] == class_name]
    return sorted(list(set(semesters)))


def get_unique_subjects(class_name, semester):
    """Получить список предметов для выбранного класса и полугодия"""
    subjects = [
        item["предмет"] for item in schedule_data
        if item["класс"] == class_name and item["полугодие"] == semester
    ]
    return sorted(list(set(subjects)))


def get_subject_info(class_name, semester, subject):
    """Получить информацию о предмете"""
    for item in schedule_data:
        if (item["класс"] == class_name and
                item["полугодие"] == semester and
                item["предмет"] == subject):
            return item["информация"]
    return "Информация не найдена"


# Функция для создания клавиатуры
def create_keyboard(items, callback_prefix):
    """Создать inline клавиатуру из списка элементов"""
    keyboard = []
    for item in items:
        keyboard.append([InlineKeyboardButton(
            text=item,
            callback_data=f"{callback_prefix}:{item}"
        )])
    # Добавляем кнопку "Назад" если это не первое меню
    if callback_prefix != "class":
        keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Обработчик команды /start
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    classes = get_unique_classes()
    if not classes:
        await message.answer("❌ Данные о классах отсутствуют")
        return

    # Добавляем информацию о админских командах для админов
    admin_text = ""
    if is_admin(message.from_user.id):
        admin_text = (
            "\n\n🔧 <b>Админские команды:</b>\n"
            "/add - Добавить запись\n"
            "/delete - Удалить запись\n"
            "/edit - Редактировать запись\n"
            "/list - Все записи\n"
            "/addadmin - Добавить админа\n"
            "/listadmins - Список админов\n"
            "/removeadmin - Удалить админа\n"
            "/stats - Статистика\n"
            "/search - Поиск по базе"
        )

    keyboard = create_keyboard(classes, "class")
    await message.answer(
        f"📚 Добро пожаловать в бот расписания!{admin_text}\n\n"
        "Выберите класс:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(ScheduleStates.choosing_class)


# Обработчик выбора класса
@dp.callback_query(F.data.startswith("class:"))
async def process_class_selection(callback: CallbackQuery, state: FSMContext):
    class_name = callback.data.split(":")[1]
    await state.update_data(class_name=class_name)

    semesters = get_unique_semesters(class_name)
    if not semesters:
        await callback.message.edit_text("❌ Данные о полугодиях отсутствуют")
        return

    keyboard = create_keyboard(semesters, "semester")
    await callback.message.edit_text(
        f"Класс: {class_name}\n\n"
        "Выберите полугодие:",
        reply_markup=keyboard
    )
    await state.set_state(ScheduleStates.choosing_semester)
    await callback.answer()


# Обработчик выбора полугодия
@dp.callback_query(F.data.startswith("semester:"))
async def process_semester_selection(callback: CallbackQuery, state: FSMContext):
    semester = callback.data.split(":")[1]
    data = await state.get_data()
    class_name = data.get("class_name")

    await state.update_data(semester=semester)

    subjects = get_unique_subjects(class_name, semester)
    if not subjects:
        await callback.message.edit_text("❌ Предметы не найдены")
        return

    keyboard = create_keyboard(subjects, "subject")
    await callback.message.edit_text(
        f"Класс: {class_name}\n"
        f"Полугодие: {semester}\n\n"
        "Выберите предмет:",
        reply_markup=keyboard
    )
    await state.set_state(ScheduleStates.choosing_subject)
    await callback.answer()


# Обработчик выбора предмета
@dp.callback_query(F.data.startswith("subject:"))
async def process_subject_selection(callback: CallbackQuery, state: FSMContext):
    subject = callback.data.split(":")[1]
    data = await state.get_data()
    class_name = data.get("class_name")
    semester = data.get("semester")

    info = get_subject_info(class_name, semester, subject)

    # Клавиатура с кнопкой "Назад" и "В начало"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К предметам", callback_data="back_to_subjects")],
        [InlineKeyboardButton(text="🏠 В начало", callback_data="back_to_start")]
    ])

    await callback.message.edit_text(
        f"📖 Класс: {class_name}\n"
        f"📅 Полугодие: {semester}\n"
        f"📝 Предмет: {subject}\n\n"
        f"ℹ️ Информация:\n{info}",
        reply_markup=keyboard
    )
    await callback.answer()


# Обработчик кнопки "Назад"
@dp.callback_query(F.data == "back")
async def process_back(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()

    if current_state == ScheduleStates.choosing_semester:
        # Возврат к выбору класса
        classes = get_unique_classes()
        keyboard = create_keyboard(classes, "class")
        await callback.message.edit_text(
            "📚 Выберите класс:",
            reply_markup=keyboard
        )
        await state.set_state(ScheduleStates.choosing_class)

    elif current_state == ScheduleStates.choosing_subject:
        # Возврат к выбору полугодия
        data = await state.get_data()
        class_name = data.get("class_name")
        semesters = get_unique_semesters(class_name)
        keyboard = create_keyboard(semesters, "semester")
        await callback.message.edit_text(
            f"Класс: {class_name}\n\n"
            "Выберите полугодие:",
            reply_markup=keyboard
        )
        await state.set_state(ScheduleStates.choosing_semester)

    await callback.answer()


# Обработчик кнопки "Назад к предметам"
@dp.callback_query(F.data == "back_to_subjects")
async def process_back_to_subjects(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    class_name = data.get("class_name")
    semester = data.get("semester")

    subjects = get_unique_subjects(class_name, semester)
    keyboard = create_keyboard(subjects, "subject")
    await callback.message.edit_text(
        f"Класс: {class_name}\n"
        f"Полугодие: {semester}\n\n"
        "Выберите предмет:",
        reply_markup=keyboard
    )
    await state.set_state(ScheduleStates.choosing_subject)
    await callback.answer()


# Обработчик кнопки "В начало"
@dp.callback_query(F.data == "back_to_start")
async def process_back_to_start(callback: CallbackQuery, state: FSMContext):
    classes = get_unique_classes()
    keyboard = create_keyboard(classes, "class")
    await callback.message.edit_text(
        "📚 Выберите класс:",
        reply_markup=keyboard
    )
    await state.set_state(ScheduleStates.choosing_class)
    await callback.answer()


# ========== АДМИНСКИЕ КОМАНДЫ ==========

# Команда добавления новой записи
@dp.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return

    await message.answer(
        "➕ <b>Добавление новой записи</b>\n\n"
        "Введите название класса (например: 9А, 10Б):",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.adding_class)


@dp.message(AdminStates.adding_class)
async def process_add_class(message: Message, state: FSMContext):
    await state.update_data(new_class=message.text.strip())
    await message.answer("Введите номер полугодия (1 или 2):")
    await state.set_state(AdminStates.adding_semester)


@dp.message(AdminStates.adding_semester)
async def process_add_semester(message: Message, state: FSMContext):
    semester = message.text.strip()
    if semester not in ["1", "2"]:
        await message.answer("❌ Полугодие должно быть 1 или 2. Попробуйте снова:")
        return

    await state.update_data(new_semester=semester)
    await message.answer("Введите название предмета:")
    await state.set_state(AdminStates.adding_subject)


@dp.message(AdminStates.adding_subject)
async def process_add_subject(message: Message, state: FSMContext):
    await state.update_data(new_subject=message.text.strip())
    await message.answer(
        "Введите информацию о предмете:\n"
        "(учитель, кабинет, учебник и т.д.)"
    )
    await state.set_state(AdminStates.adding_info)


@dp.message(AdminStates.adding_info)
async def process_add_info(message: Message, state: FSMContext):
    data = await state.get_data()

    new_entry = {
        "класс": data["new_class"],
        "полугодие": data["new_semester"],
        "предмет": data["new_subject"],
        "информация": message.text.strip()
    }

    schedule_data.append(new_entry)
    save_data()

    await message.answer(
        f"✅ <b>Запись успешно добавлена!</b>\n\n"
        f"Класс: {new_entry['класс']}\n"
        f"Полугодие: {new_entry['полугодие']}\n"
        f"Предмет: {new_entry['предмет']}\n"
        f"Информация: {new_entry['информация']}\n\n"
        f"Используйте /add для добавления еще одной записи",
        parse_mode="HTML"
    )
    await state.clear()


# Команда добавления администратора
@dp.message(Command("addadmin"))
async def cmd_add_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return

    await message.answer(
        "🔐 <b>Добавление администратора</b>\n\n"
        "Введите ID пользователя, которого хотите сделать администратором:\n\n"
        "<i>Примечание: пользователь может узнать свой ID у бота @userinfobot</i>",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.adding_admin_id)


@dp.message(AdminStates.adding_admin_id)
async def process_add_admin(message: Message, state: FSMContext):
    try:
        new_admin_id = int(message.text.strip())

        if new_admin_id in ADMIN_IDS:
            await message.answer("⚠️ Этот пользователь уже является администратором")
        else:
            ADMIN_IDS.append(new_admin_id)
            await message.answer(
                f"✅ Пользователь с ID <code>{new_admin_id}</code> добавлен в администраторы!\n\n"
                f"⚠️ <b>Внимание:</b> это изменение действует только до перезапуска бота",
                parse_mode="HTML"
            )
    except ValueError:
        await message.answer("❌ Ошибка: ID должен быть числом. Попробуйте снова:")
        return

    await state.clear()


# Команда просмотра списка администраторов
@dp.message(Command("listadmins"))
async def cmd_list_admins(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return

    admin_list = "\n".join([f"• <code>{admin_id}</code>" for admin_id in ADMIN_IDS])
    await message.answer(
        f"👥 <b>Список администраторов:</b>\n\n{admin_list}",
        parse_mode="HTML"
    )


# Команда удаления администратора
@dp.message(Command("removeadmin"))
async def cmd_remove_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return

    try:
        admin_id = int(message.text.split()[1])

        if admin_id not in ADMIN_IDS:
            await message.answer("⚠️ Этот пользователь не является администратором")
        elif len(ADMIN_IDS) == 1:
            await message.answer("❌ Нельзя удалить последнего администратора")
        else:
            ADMIN_IDS.remove(admin_id)
            await message.answer(
                f"✅ Администратор с ID <code>{admin_id}</code> удален\n\n"
                f"⚠️ <b>Внимание:</b> это изменение действует только до перезапуска бота",
                parse_mode="HTML"
            )
    except (IndexError, ValueError):
        await message.answer(
            "Использование: /removeadmin ID\n"
            "Пример: /removeadmin 123456789"
        )


# Команда просмотра всех записей (для админов)
@dp.message(Command("list"))
async def cmd_list(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return

    if not schedule_data:
        await message.answer("📭 База данных пуста")
        return

    text = "📋 <b>Все записи в базе данных:</b>\n\n"
    for i, entry in enumerate(schedule_data, 1):
        text += (
            f"{i}. Класс: {entry['класс']}, "
            f"Полугодие: {entry['полугодие']}, "
            f"Предмет: {entry['предмет']}\n"
        )

    text += f"\n<b>Всего записей:</b> {len(schedule_data)}"
    await message.answer(text, parse_mode="HTML")


# Запуск бота
async def main():
    # Загружаем только данные расписания при запуске
    load_data()

    print("Бот запущен!")
    print(f"Администраторов: {len(ADMIN_IDS)}")
    print(f"Записей в базе: {len(schedule_data)}")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())