#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import json
import os
from datetime import datetime
from typing import List, Dict, Any

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Конфиг - создайте файл config.py рядом с этим скриптом:
# BOT_TOKEN = "ТОКЕН"
# ADMIN_IDS = [12345678, 87654321]
from config import ADMIN_IDS, BOT_TOKEN

# -------------------------
# Данные по умолчанию
# -------------------------
schedule_data: List[Dict[str, Any]] = [
    {
        "класс": "9А",
        "полугодие": "1",
        "предмет": "Математика",
        "экзамен": "Зачёт",
        "тип_материалов": "Формулы",
        "информация": "Учебник: Алгебра 9 класс\nУчитель: Иванов И.И.\nКабинет: 205",
        "ссылка": "https://example.com/math-materials"
    },
]

DATA_FILE = "schedule_data.json"
BACKUP_DIR = "backups"

# -------------------------
# FSM состояния
# -------------------------
class ScheduleStates(StatesGroup):
    choosing_class = State()
    choosing_semester = State()
    choosing_subject = State()
    choosing_exam = State()
    choosing_material_type = State()


class AdminStates(StatesGroup):
    adding_class = State()
    adding_semester = State()
    adding_subject = State()
    adding_exam = State()
    adding_material_type = State()
    adding_info = State()
    adding_link = State()

    deleting_record = State()
    deleting_confirm = State()

    editing_select_record = State()
    editing_field = State()
    editing_value = State()

    adding_admin_id = State()

    importing_data = State()
    exporting_data = State()
    backup_create = State()

# -------------------------
# Инициализация бота
# -------------------------
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# -------------------------
# Хелперы сохранения/загрузки
# -------------------------
def save_data():
    """Сохранить данные в файл"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(schedule_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения данных: {e}")


def load_data():
    """Загрузить данные из файла"""
    global schedule_data
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                schedule_data = json.load(f)
        else:
            save_data()
    except Exception as e:
        print(f"Ошибка загрузки данных: {e}")


def ensure_backup_dir():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)


# -------------------------
# Утилиты
# -------------------------
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def get_unique_classes():
    return sorted(list({item["класс"] for item in schedule_data}))


def get_unique_semesters(class_name):
    semesters = [item["полугодие"] for item in schedule_data if item["класс"] == class_name]
    return sorted(list(set(semesters)))


def get_unique_subjects(class_name, semester):
    subjects = [
        item["предмет"] for item in schedule_data
        if item["класс"] == class_name and item["полугодие"] == semester
    ]
    return sorted(list(set(subjects)))


def get_unique_exams(class_name, semester, subject):
    exams = [
        item["экзамен"] for item in schedule_data
        if item["класс"] == class_name and item["полугодие"] == semester and item["предмет"] == subject
    ]
    return sorted(list(set(exams)))


def get_unique_material_types(class_name, semester, subject, exam):
    materials = [
        item["тип_материалов"] for item in schedule_data
        if (item["класс"] == class_name and item["полугодие"] == semester and
            item["предмет"] == subject and item["экзамен"] == exam)
    ]
    return sorted(list(set(materials)))


def get_full_info(class_name, semester, subject, exam, material_type):
    for item in schedule_data:
        if (item["класс"] == class_name and item["полугодие"] == semester and
                item["предмет"] == subject and item["экзамен"] == exam and
                item["тип_материалов"] == material_type):
            return item
    return None


def create_keyboard(items: List[str], callback_prefix: str, add_back=True) -> InlineKeyboardMarkup:
    keyboard = []
    for item in items:
        keyboard.append([InlineKeyboardButton(text=item, callback_data=f"{callback_prefix}:{item}")])

    if add_back and callback_prefix != "class":
        keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def format_info_card(record: Dict[str, Any]) -> str:
    card = (
        "╔═══════════════════════════╗\n"
        "║   📋 <b>ИНФОРМАЦИЯ О ПРЕДМЕТЕ</b>   ║\n"
        "╚═══════════════════════════╝\n\n"
        f"🏫 <b>Класс:</b> <code>{record['класс']}</code>\n"
        f"📅 <b>Полугодие:</b> <code>{record['полугодие']}</code>\n"
        f"📚 <b>Предмет:</b> <code>{record['предмет']}</code>\n"
        f"📝 <b>Тип экзамена:</b> <code>{record['экзамен']}</code>\n"
        f"📄 <b>Справочные материалы:</b> <code>{record['тип_материалов']}</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"ℹ️ <b>Дополнительная информация:</b>\n"
        f"<pre>{record['информация']}</pre>\n"
    )

    if record.get('ссылка'):
        card += f"\n🔗 <b>Ссылка на материалы:</b>\n{record['ссылка']}"

    return card


# -------------------------
# Загрузка данных при старте
# -------------------------
load_data()
ensure_backup_dir()

# -------------------------
# Основные handlers
# -------------------------
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    classes = get_unique_classes()

    if not classes:
        await message.answer("❌ <b>База данных пуста</b>\n\nОбратитесь к администратору.", parse_mode="HTML")
        return

    admin_text = ""
    if is_admin(message.from_user.id):
        admin_text = (
            "\n\n╔═══════════════════════════╗\n"
            "║   🔧 <b>ПАНЕЛЬ АДМИНИСТРАТОРА</b>   ║\n"
            "╚═══════════════════════════╝\n"
            "/add - Добавить запись\n"
            "/delete - Удалить запись\n"
            "/edit - Редактировать запись\n"
            "/list - Все записи\n"
            "/stats - Статистика\n"
            "/search - Поиск\n"
            "/export - Экспорт данных\n"
            "/import - Импорт данных\n"
            "/addadmin - Добавить админа\n"
            "/listadmins - Список админов\n"
            "/backup - Резервная копия"
        )

    keyboard = create_keyboard(classes, "class", add_back=False)

    welcome_text = (
        "╔═══════════════════════════╗\n"
        "║   📚 <b>БОТ РАСПИСАНИЯ</b>   ║\n"
        "╚═══════════════════════════╝\n\n"
        "👋 Добро пожаловать!\n\n"
        "Выберите класс для начала работы:"
        f"{admin_text}"
    )

    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(ScheduleStates.choosing_class)


# выбор класса -> полугодие
@dp.callback_query(F.data.startswith("class:"))
async def process_class_selection(callback: CallbackQuery, state: FSMContext):
    class_name = callback.data.split(":", 1)[1]
    await state.update_data(class_name=class_name)

    semesters = get_unique_semesters(class_name)
    if not semesters:
        await callback.message.edit_text("❌ Данные о полугодиях отсутствуют")
        await callback.answer()
        return

    keyboard = create_keyboard(semesters, "semester")
    await callback.message.edit_text(
        f"✅ <b>Выбран класс:</b> <code>{class_name}</code>\n\n"
        f"📅 Выберите полугодие:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(ScheduleStates.choosing_semester)
    await callback.answer()


# выбор полугодия -> предмет
@dp.callback_query(F.data.startswith("semester:"))
async def process_semester_selection(callback: CallbackQuery, state: FSMContext):
    semester = callback.data.split(":", 1)[1]
    data = await state.get_data()
    class_name = data.get("class_name")

    await state.update_data(semester=semester)

    subjects = get_unique_subjects(class_name, semester)
    if not subjects:
        await callback.message.edit_text("❌ Предметы не найдены")
        await callback.answer()
        return

    keyboard = create_keyboard(subjects, "subject")
    await callback.message.edit_text(
        f"🏫 <b>Класс:</b> <code>{class_name}</code>\n"
        f"📅 <b>Полугодие:</b> <code>{semester}</code>\n\n"
        f"📚 Выберите предмет:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(ScheduleStates.choosing_subject)
    await callback.answer()


# выбор предмета -> тип экзамена
@dp.callback_query(F.data.startswith("subject:"))
async def process_subject_selection(callback: CallbackQuery, state: FSMContext):
    subject = callback.data.split(":", 1)[1]
    data = await state.get_data()
    class_name = data.get("class_name")
    semester = data.get("semester")

    await state.update_data(subject=subject)

    exams = get_unique_exams(class_name, semester, subject)
    if not exams:
        await callback.message.edit_text("❌ Типы экзаменов не найдены")
        await callback.answer()
        return

    keyboard = create_keyboard(exams, "exam")
    await callback.message.edit_text(
        f"🏫 <b>Класс:</b> <code>{class_name}</code>\n"
        f"📅 <b>Полугодие:</b> <code>{semester}</code>\n"
        f"📚 <b>Предмет:</b> <code>{subject}</code>\n\n"
        f"📝 Выберите тип экзамена:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(ScheduleStates.choosing_exam)
    await callback.answer()


# выбор экзамена -> тип материалов
@dp.callback_query(F.data.startswith("exam:"))
async def process_exam_selection(callback: CallbackQuery, state: FSMContext):
    exam = callback.data.split(":", 1)[1]
    data = await state.get_data()
    class_name = data.get("class_name")
    semester = data.get("semester")
    subject = data.get("subject")

    await state.update_data(exam=exam)

    material_types = get_unique_material_types(class_name, semester, subject, exam)
    if not material_types:
        await callback.message.edit_text("❌ Типы справочных материалов не найдены")
        await callback.answer()
        return

    keyboard = create_keyboard(material_types, "material")
    await callback.message.edit_text(
        f"🏫 <b>Класс:</b> <code>{class_name}</code>\n"
        f"📅 <b>Полугодие:</b> <code>{semester}</code>\n"
        f"📚 <b>Предмет:</b> <code>{subject}</code>\n"
        f"📝 <b>Экзамен:</b> <code>{exam}</code>\n\n"
        f"📄 Выберите тип справочных материалов:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(ScheduleStates.choosing_material_type)
    await callback.answer()


# выбор типа материалов -> карточка
@dp.callback_query(F.data.startswith("material:"))
async def process_material_selection(callback: CallbackQuery, state: FSMContext):
    material_type = callback.data.split(":", 1)[1]
    data = await state.get_data()

    record = get_full_info(
        data.get("class_name"),
        data.get("semester"),
        data.get("subject"),
        data.get("exam"),
        material_type
    )

    if not record:
        await callback.message.edit_text("❌ Информация не найдена")
        await callback.answer()
        return

    # клавиатура
    keyboard_buttons = [
        [InlineKeyboardButton(text="⬅️ К типам материалов", callback_data="back_to_materials")],
        [InlineKeyboardButton(text="🏠 В начало", callback_data="back_to_start")]
    ]

    if record.get('ссылка'):
        keyboard_buttons.insert(0, [InlineKeyboardButton(text="🔗 Получить материалы", url=record['ссылка'])])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(
        format_info_card(record),
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(ScheduleStates.choosing_material_type)
    await callback.answer()


# назад (универсальная кнопка)
@dp.callback_query(F.data == "back")
async def process_back(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    data = await state.get_data()

    if current_state == ScheduleStates.choosing_semester.state:
        classes = get_unique_classes()
        keyboard = create_keyboard(classes, "class", add_back=False)
        await callback.message.edit_text("📚 Выберите класс:", reply_markup=keyboard, parse_mode="HTML")
        await state.set_state(ScheduleStates.choosing_class)

    elif current_state == ScheduleStates.choosing_subject.state:
        class_name = data.get("class_name")
        semesters = get_unique_semesters(class_name)
        keyboard = create_keyboard(semesters, "semester")
        await callback.message.edit_text(
            f"✅ <b>Выбран класс:</b> <code>{class_name}</code>\n\n📅 Выберите полугодие:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await state.set_state(ScheduleStates.choosing_semester)

    elif current_state == ScheduleStates.choosing_exam.state:
        class_name = data.get("class_name")
        semester = data.get("semester")
        subjects = get_unique_subjects(class_name, semester)
        keyboard = create_keyboard(subjects, "subject")
        await callback.message.edit_text(
            f"🏫 <b>Класс:</b> <code>{class_name}</code>\n"
            f"📅 <b>Полугодие:</b> <code>{semester}</code>\n\n📚 Выберите предмет:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await state.set_state(ScheduleStates.choosing_subject)

    elif current_state == ScheduleStates.choosing_material_type.state:
        class_name = data.get("class_name")
        semester = data.get("semester")
        subject = data.get("subject")
        exams = get_unique_exams(class_name, semester, subject)
        keyboard = create_keyboard(exams, "exam")
        await callback.message.edit_text(
            f"🏫 <b>Класс:</b> <code>{class_name}</code>\n"
            f"📅 <b>Полугодие:</b> <code>{semester}</code>\n"
            f"📚 <b>Предмет:</b> <code>{subject}</code>\n\n📝 Выберите тип экзамена:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await state.set_state(ScheduleStates.choosing_exam)

    await callback.answer()


@dp.callback_query(F.data == "back_to_materials")
async def process_back_to_materials(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    material_types = get_unique_material_types(
        data.get("class_name"),
        data.get("semester"),
        data.get("subject"),
        data.get("exam")
    )
    keyboard = create_keyboard(material_types, "material")
    await callback.message.edit_text(
        f"📄 Выберите тип справочных материалов:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(ScheduleStates.choosing_material_type)
    await callback.answer()


@dp.callback_query(F.data == "back_to_start")
async def process_back_to_start(callback: CallbackQuery, state: FSMContext):
    classes = get_unique_classes()
    keyboard = create_keyboard(classes, "class", add_back=False)
    await callback.message.edit_text("📚 Выберите класс:", reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(ScheduleStates.choosing_class)
    await callback.answer()


# -------------------------
# АДМИН: ADD (уже был, немного улучшен)
# -------------------------
@dp.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return

    await message.answer(
        "╔═══════════════════════════╗\n"
        "║   ➕ <b>ДОБАВЛЕНИЕ ЗАПИСИ</b>   ║\n"
        "╚═══════════════════════════╝\n\n"
        "Введите название класса (например: 9А, 10Б) или 0 для отмены:",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.adding_class)


@dp.message(AdminStates.adding_class)
async def process_add_class(message: Message, state: FSMContext):
    if message.text.strip() == "0":
        await message.answer("❌ Добавление отменено.")
        await state.clear()
        return

    await state.update_data(new_class=message.text.strip())
    await message.answer("📅 Введите номер полугодия (1 или 2) или 0 для отмены:")
    await state.set_state(AdminStates.adding_semester)


@dp.message(AdminStates.adding_semester)
async def process_add_semester(message: Message, state: FSMContext):
    if message.text.strip() == "0":
        await message.answer("❌ Добавление отменено.")
        await state.clear()
        return

    semester = message.text.strip()
    if semester not in ["1", "2"]:
        await message.answer("❌ Полугодие должно быть 1 или 2. Попробуйте снова:")
        return

    await state.update_data(new_semester=semester)
    await message.answer("📚 Введите название предмета или 0 для отмены:")
    await state.set_state(AdminStates.adding_subject)


@dp.message(AdminStates.adding_subject)
async def process_add_subject(message: Message, state: FSMContext):
    if message.text.strip() == "0":
        await message.answer("❌ Добавление отменено.")
        await state.clear()
        return

    await state.update_data(new_subject=message.text.strip())
    await message.answer("📝 Введите тип экзамена (Зачёт, Семестровая, Контрольная и т.д.) или 0 для отмены:")
    await state.set_state(AdminStates.adding_exam)


@dp.message(AdminStates.adding_exam)
async def process_add_exam(message: Message, state: FSMContext):
    if message.text.strip() == "0":
        await message.answer("❌ Добавление отменено.")
        await state.clear()
        return

    await state.update_data(new_exam=message.text.strip())
    await message.answer("📄 Введите тип справочных материалов (Формулы, Таблицы, Конспекты и т.д.) или 0 для отмены:")
    await state.set_state(AdminStates.adding_material_type)


@dp.message(AdminStates.adding_material_type)
async def process_add_material_type(message: Message, state: FSMContext):
    if message.text.strip() == "0":
        await message.answer("❌ Добавление отменено.")
        await state.clear()
        return

    await state.update_data(new_material_type=message.text.strip())
    await message.answer(
        "ℹ️ Введите дополнительную информацию о предмете:\n"
        "(учитель, кабинет, учебник и т.д.) или 0 для отмены"
    )
    await state.set_state(AdminStates.adding_info)


@dp.message(AdminStates.adding_info)
async def process_add_info(message: Message, state: FSMContext):
    if message.text.strip() == "0":
        await message.answer("❌ Добавление отменено.")
        await state.clear()
        return

    await state.update_data(new_info=message.text.strip())
    await message.answer(
        "🔗 Введите ссылку на материалы (или напишите 'нет', если ссылки нет) или 0 для отмены:"
    )
    await state.set_state(AdminStates.adding_link)


@dp.message(AdminStates.adding_link)
async def process_add_link(message: Message, state: FSMContext):
    if message.text.strip() == "0":
        await message.answer("❌ Добавление отменено.")
        await state.clear()
        return

    data = await state.get_data()
    link = message.text.strip() if message.text.strip().lower() != "нет" else ""

    new_entry = {
        "класс": data["new_class"],
        "полугодие": data["new_semester"],
        "предмет": data["new_subject"],
        "экзамен": data["new_exam"],
        "тип_материалов": data["new_material_type"],
        "информация": data["new_info"],
        "ссылка": link
    }

    schedule_data.append(new_entry)
    save_data()

    await message.answer(
        "╔═══════════════════════════╗\n"
        "║   ✅ <b>ЗАПИСЬ ДОБАВЛЕНА</b>   ║\n"
        "╚═══════════════════════════╝\n\n"
        f"🏫 <b>Класс:</b> <code>{new_entry['класс']}</code>\n"
        f"📅 <b>Полугодие:</b> <code>{new_entry['полугодие']}</code>\n"
        f"📚 <b>Предмет:</b> <code>{new_entry['предмет']}</code>\n"
        f"📝 <b>Экзамен:</b> <code>{new_entry['экзамен']}</code>\n"
        f"📄 <b>Материалы:</b> <code>{new_entry['тип_материалов']}</code>\n"
        f"🔗 <b>Ссылка:</b> {new_entry['ссылка'] or 'Нет'}\n\n"
        "Используйте /add для добавления еще одной записи",
        parse_mode="HTML"
    )
    await state.clear()


# -------------------------
# АДМИН: LIST
# -------------------------
@dp.message(Command("list"))
async def cmd_list(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return

    if not schedule_data:
        await message.answer("📭 База данных пуста")
        return

    text = "╔═══════════════════════════╗\n║   📋 <b>ВСЕ ЗАПИСИ</b>   ║\n╚═══════════════════════════╝\n\n"
    for i, entry in enumerate(schedule_data, 1):
        text += (
            f"{i}. {entry['класс']} | {entry['предмет']} | "
            f"{entry['экзамен']} | {entry['тип_материалов']}\n"
        )

    text += f"\n<b>Всего записей:</b> {len(schedule_data)}"
    await message.answer(text, parse_mode="HTML")


# -------------------------
# АДМИН: DELETE
# -------------------------
@dp.message(Command("delete"))
async def cmd_delete(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return

    if not schedule_data:
        await message.answer("📭 База данных пуста")
        return

    # Показываем список с номерами
    text = "╔═══════════════════════════╗\n║   🗑️ <b>УДАЛЕНИЕ ЗАПИСИ</b>   ║\n╚═══════════════════════════╝\n\n"
    text += "Введите номер записи для удаления (или 0 для отмены):\n\n"
    for i, entry in enumerate(schedule_data, 1):
        text += f"{i}. {entry['класс']} | {entry['предмет']} | {entry['экзамен']} | {entry['тип_материалов']}\n"

    await message.answer(text, parse_mode="HTML")
    await state.set_state(AdminStates.deleting_record)


@dp.message(AdminStates.deleting_record)
async def process_delete_choice(message: Message, state: FSMContext):
    if message.text.strip() == "0":
        await message.answer("❌ Удаление отменено.")
        await state.clear()
        return

    try:
        idx = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите корректный номер записи:")
        return

    if not (1 <= idx <= len(schedule_data)):
        await message.answer("❌ Номер вне диапазона. Попробуйте снова:")
        return

    await state.update_data(delete_index=idx - 1)
    entry = schedule_data[idx - 1]
    await message.answer(
        "⚠️ Вы подтверждаете удаление записи:\n\n"
        f"🏫 <b>{entry['класс']}</b> | {entry['предмет']} | {entry['экзамен']} | {entry['тип_материалов']}\n\n"
        "Напишите 'ДА' для подтверждения или 0 для отмены.",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.deleting_confirm)


@dp.message(AdminStates.deleting_confirm)
async def process_delete_confirm(message: Message, state: FSMContext):
    if message.text.strip() == "0":
        await message.answer("❌ Удаление отменено.")
        await state.clear()
        return

    if message.text.strip().lower() != "да":
        await message.answer("❌ Для удаления нужно написать 'ДА' или 0 для отмены.")
        return

    data = await state.get_data()
    idx = data.get("delete_index")
    if idx is None or not (0 <= idx < len(schedule_data)):
        await message.answer("❌ Ошибка. Запись не найдена.")
        await state.clear()
        return

    removed = schedule_data.pop(idx)
    save_data()
    await message.answer(
        "✅ Запись успешно удалена:\n"
        f"🏫 <b>{removed['класс']}</b> | {removed['предмет']} | {removed['экзамен']} | {removed['тип_материалов']}",
        parse_mode="HTML"
    )
    await state.clear()


# -------------------------
# АДМИН: EDIT
# -------------------------
EDITABLE_FIELDS = {
    "1": "класс",
    "2": "полугодие",
    "3": "предмет",
    "4": "экзамен",
    "5": "тип_материалов",
    "6": "информация",
    "7": "ссылка"
}


@dp.message(Command("edit"))
async def cmd_edit(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return

    if not schedule_data:
        await message.answer("📭 База данных пуста")
        return

    text = "╔═══════════════════════════╗\n║   ✏️ <b>РЕДАКТИРОВАНИЕ ЗАПИСИ</b>   ║\n╚═══════════════════════════╝\n\n"
    text += "Введите номер записи для редактирования (или 0 для отмены):\n\n"
    for i, entry in enumerate(schedule_data, 1):
        text += f"{i}. {entry['класс']} | {entry['предмет']} | {entry['экзамен']} | {entry['тип_материалов']}\n"

    await message.answer(text, parse_mode="HTML")
    await state.set_state(AdminStates.editing_select_record)


@dp.message(AdminStates.editing_select_record)
async def process_edit_select(message: Message, state: FSMContext):
    if message.text.strip() == "0":
        await message.answer("❌ Редактирование отменено.")
        await state.clear()
        return

    try:
        idx = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите корректный номер записи:")
        return

    if not (1 <= idx <= len(schedule_data)):
        await message.answer("❌ Номер вне диапазона. Попробуйте снова:")
        return

    await state.update_data(edit_index=idx - 1)
    text = "Выберите поле для редактирования:\n"
    text += "1. класс\n2. полугодие\n3. предмет\n4. экзамен\n5. тип_материалов\n6. информация\n7. ссылка\n\nВведите цифру поля (или 0 для отмены):"
    await message.answer(text)
    await state.set_state(AdminStates.editing_field)


@dp.message(AdminStates.editing_field)
async def process_edit_field(message: Message, state: FSMContext):
    if message.text.strip() == "0":
        await message.answer("❌ Редактирование отменено.")
        await state.clear()
        return

    choice = message.text.strip()
    if choice not in EDITABLE_FIELDS:
        await message.answer("❌ Некорректный выбор. Введите цифру поля от 1 до 7:")
        return

    await state.update_data(edit_field=EDITABLE_FIELDS[choice])
    await message.answer("Введите новое значение (или 0 для отмены):")
    await state.set_state(AdminStates.editing_value)


@dp.message(AdminStates.editing_value)
async def process_edit_value(message: Message, state: FSMContext):
    if message.text.strip() == "0":
        await message.answer("❌ Редактирование отменено.")
        await state.clear()
        return

    data = await state.get_data()
    idx = data.get("edit_index")
    field = data.get("edit_field")
    new_value = message.text.strip()

    if idx is None or field is None:
        await message.answer("❌ Ошибка состояния. Попробуйте снова.")
        await state.clear()
        return

    old_value = schedule_data[idx].get(field, "")
    schedule_data[idx][field] = new_value
    save_data()

    await message.answer(
        "✅ Запись обновлена.\n\n"
        f"Поле: <b>{field}</b>\n"
        f"Было: <pre>{old_value}</pre>\n"
        f"Стало: <pre>{new_value}</pre>",
        parse_mode="HTML"
    )
    await state.clear()


# -------------------------
# SEARCH (улучшенный)
# -------------------------
@dp.message(Command("search"))
async def cmd_search(message: Message):
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await message.answer(
            "🔍 <b>Поиск по базе</b>\n"
            "Использование: <code>/search запрос</code>\n"
            "Пример: /search Математика",
            parse_mode="HTML"
        )
        return

    query = args[1].lower()
    found_records = []

    for entry in schedule_data:
        # Проверяем все поля, приводя к строке
        concatenated = " ".join(str(v).lower() for v in entry.values())
        if query in concatenated:
            found_records.append(entry)

    if not found_records:
        await message.answer(f"😔 По запросу «{args[1]}» ничего не найдено.")
        return

    text = f"🔎 <b>Найдено записей: {len(found_records)}</b>\n\n"
    for entry in found_records:
        text += (
            f"🔹 <b>{entry['класс']}</b> ({entry['полугодие']} п/г) — {entry['предмет']}\n"
            f"   └ {entry['экзамен']} | {entry['тип_материалов']}\n\n"
        )

    await message.answer(text, parse_mode="HTML")


# -------------------------
# HELP
# -------------------------
@dp.message(Command("help"))
async def cmd_help(message: Message):
    user_text = (
        "╔═══════════════════════════╗\n"
        "║   🤖 <b>СПРАВКА</b>   ║\n"
        "╚═══════════════════════════╝\n\n"
        "/start - Начать работу\n"
        "/search - Поиск по базе\n"
        "/help - Эта справка\n"
    )

    admin_text = (
        "\n\n⚙️ <b>Команды администратора:</b>\n"
        "/add - Добавить запись\n"
        "/delete - Удалить запись\n"
        "/edit - Редактировать запись\n"
        "/list - Список всех записей\n"
        "/stats - Статистика базы\n"
        "/export - Экспорт базы (JSON)\n"
        "/import - Импорт базы (JSON)\n"
        "/backup - Создать резервную копию\n"
        "/addadmin - Добавить админа\n"
        "/listadmins - Список админов\n"
        "/analytics - Простая аналитика\n"
        "/notify - Отправить тестовое уведомление (адм.)"
    )

    text = user_text
    if is_admin(message.from_user.id):
        text += admin_text

    await message.answer(text, parse_mode="HTML")


# -------------------------
# STATS
# -------------------------
@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Только для администраторов")
        return

    total_records = len(schedule_data)
    unique_classes = get_unique_classes()
    unique_subjects = set(item['предмет'] for item in schedule_data)
    unique_exams = set(item['экзамен'] for item in schedule_data)

    class_stats = ""
    for cls in unique_classes:
        count = sum(1 for item in schedule_data if item['класс'] == cls)
        class_stats += f"• {cls}: {count} записей\n"

    text = (
        "╔═══════════════════════════╗\n"
        "║   📊 <b>СТАТИСТИКА</b>   ║\n"
        "╚═══════════════════════════╝\n\n"
        f"📚 Всего записей: <b>{total_records}</b>\n"
        f"🏫 Классов: <b>{len(unique_classes)}</b>\n"
        f"📝 Уникальных предметов: <b>{len(unique_subjects)}</b>\n"
        f"📋 Типов экзаменов: <b>{len(unique_exams)}</b>\n\n"
        f"<b>По классам:</b>\n{class_stats}"
    )

    await message.answer(text, parse_mode="HTML")


# -------------------------
# EXPORT / IMPORT / BACKUP
# -------------------------
@dp.message(Command("export"))
async def cmd_export(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Только для администраторов")
        return

    # Убедимся, что данные сохранены
    save_data()
    await message.answer_document(InputFile(DATA_FILE), caption="📤 Экспорт базы данных (JSON)")


@dp.message(Command("backup"))
async def cmd_backup(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Только для администраторов")
        return

    ensure_backup_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = os.path.join(BACKUP_DIR, f"backup_{timestamp}.json")
    try:
        with open(backup_name, 'w', encoding='utf-8') as f:
            json.dump(schedule_data, f, ensure_ascii=False, indent=2)
        await message.answer(f"✅ Резервная копия создана: <code>{backup_name}</code>", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка при создании бэкапа: {e}")


@dp.message(Command("import"))
async def cmd_import(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Только для администраторов")
        return

    await message.answer(
        "📥 Отправьте JSON-файл для импорта (формат как у export). Или напишите 0 для отмены."
    )
    await state.set_state(AdminStates.importing_data)


@dp.message(AdminStates.importing_data)
async def process_import_file(message: Message, state: FSMContext):
    if message.text and message.text.strip() == "0":
        await message.answer("❌ Импорт отменён.")
        await state.clear()
        return

    if not message.document:
        await message.answer("❌ Пожалуйста, прикрепите JSON-файл.")
        return

    # Скачиваем файл
    try:
        filename = "import_temp.json"
        await message.document.download(destination_file=filename)
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, list):
            await message.answer("❌ Неверный формат файла. Ожидается список записей.")
            os.remove(filename)
            await state.clear()
            return

        # Валидируем примерно структуру записей
        for i, rec in enumerate(data):
            if not all(k in rec for k in ("класс", "полугодие", "предмет", "экзамен", "тип_материалов", "информация")):
                await message.answer(f"❌ Неверная структура в записи #{i+1}. Операция прервана.")
                os.remove(filename)
                await state.clear()
                return

        # Импортируем - объединяем (можно изменить логику на замену)
        schedule_data.extend(data)
        save_data()

        os.remove(filename)
        await message.answer(f"✅ Импорт завершен. Добавлено записей: {len(data)}")
    except Exception as e:
        await message.answer(f"❌ Ошибка при импорте: {e}")
    finally:
        await state.clear()


# -------------------------
# ADMINS: addadmin / listadmins
# -------------------------
@dp.message(Command("addadmin"))
async def cmd_addadmin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Только существующие админы могут добавлять новых.")
        return

    await message.answer("Введите Telegram user_id нового администратора (только число) или 0 для отмены:")
    await state.set_state(AdminStates.adding_admin_id)


@dp.message(AdminStates.adding_admin_id)
async def process_addadmin(message: Message, state: FSMContext):
    if message.text.strip() == "0":
        await message.answer("Отмена.")
        await state.clear()
        return

    try:
        new_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите корректный числовой user_id:")
        return

    if new_id in ADMIN_IDS:
        await message.answer("❌ Этот пользователь уже администратор.")
        await state.clear()
        return

    ADMIN_IDS.append(new_id)
    # Сохранение ADMIN_IDS в файл не реализовано — можно добавить хранение конфигурации
    await message.answer(f"✅ Пользователь <code>{new_id}</code> добавлен в список администраторов.", parse_mode="HTML")
    await state.clear()


@dp.message(Command("listadmins"))
async def cmd_listadmins(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Только для администраторов")
        return

    text = "👥 <b>Список администраторов:</b>\n\n"
    for aid in ADMIN_IDS:
        text += f"• <code>{aid}</code>\n"

    await message.answer(text, parse_mode="HTML")


# -------------------------
# ANALYTICS (простейшая)
# -------------------------
@dp.message(Command("analytics"))
async def cmd_analytics(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Только для администраторов")
        return

    # Топ предметов
    subject_count = {}
    for rec in schedule_data:
        subject_count[rec['предмет']] = subject_count.get(rec['предмет'], 0) + 1

    top = sorted(subject_count.items(), key=lambda x: x[1], reverse=True)[:10]
    text = "📈 <b>Простая аналитика</b>\n\nТоп предметов по количеству записей:\n"
    for subj, cnt in top:
        text += f"• {subj}: {cnt}\n"

    await message.answer(text, parse_mode="HTML")


# -------------------------
# NOTIFY (пример: отправка уведомления всем админам или подписанным)
# -------------------------
@dp.message(Command("notify"))
async def cmd_notify(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Только для администраторов")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /notify текст_уведомления")
        return

    text = args[1]
    # Для примера: отправляем всем админам
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(aid, f"🔔 Уведомление от администратора:\n\n{text}")
        except Exception:
            pass

    await message.answer("✅ Уведомления отправлены админам.")


# -------------------------
# Обработчики ошибок и отмена
# -------------------------
@dp.message()
async def fallback_handler(message: Message):
    # Легкий fallback: подсказка
    text = "Я не распознал команду или сообщение.\n"
    text += "Используйте /help для списка команд."
    await message.answer(text)


# -------------------------
# Запуск
# -------------------------
if __name__ == "__main__":
    print("Бот запущен...")
    try:
        import asyncio
        from aiogram import exceptions

        asyncio.run(dp.start_polling(bot))
    except (KeyboardInterrupt, SystemExit):
        print("Останавливаем бота...")
