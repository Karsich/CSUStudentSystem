import asyncio
import logging
import requests

import faq_helper
from faq_helper import search_faq
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.filters import Command, Filter, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup, default_state
from aiogram.fsm.storage.memory import MemoryStorage
from config_reader import config
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(level=logging.INFO)

form_router = Router()
bot = Bot(token=config.bot_token.get_secret_value())
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
scheduler = AsyncIOScheduler()

# Credentials for login
login_url = 'http://95.174.92.220:8000/auth/login'
department_url = 'http://95.174.92.220:8000/departments'
groups_url = 'http://95.174.92.220:8000/groups'
login_data = {
    "username": "telegram",
    "email": "telegram@telegram.com",
    "fullname": "none",
    "role": "system",
    "password": "awJwnbbT"
}

# URL endpoint for FAQ
faq_url = 'http://95.174.92.220:8000/faqs'
headers = {'Content-Type': 'application/json'}
jwt_token = None

# Function to update JWT token
def update_token():
    global jwt_token
    response = requests.post(login_url, json=login_data, headers=headers)
    if response.status_code == 200:
        jwt_token = response.json().get('access_token')
        headers['Authorization'] = f'Bearer {jwt_token}'
        logging.info('JWT token updated successfully.')
    else:
        logging.error(f'Failed to update JWT token: {response.status_code} - {response.text}')

# Update token initially and then every 5 minutes
update_token()
scheduler.add_job(update_token, 'interval', minutes=5)
scheduler.start()

# States
class Form(StatesGroup):
    group = State()
    name = State()
    department = State()
    student_id = State()

with open('groups.txt', 'r', encoding='utf-8') as f:
    groups = sorted([line.strip() for line in f.readlines()])

# Keyboards
main_b = [
    [KeyboardButton(text="Подать заявку в группу")],
    [KeyboardButton(text="FAQ")]
]
verification_b = [
    [InlineKeyboardButton(text="Верификация", callback_data='fill_form')]
]
faq_b = [
    [InlineKeyboardButton(text="Просмотр всех вопросов", callback_data='view_all')],
    [InlineKeyboardButton(text="Запрос", callback_data='request')]
]
notifications_b = [
    [InlineKeyboardButton(text="Показать непрочтенные", callback_data='show_unread')],
    [InlineKeyboardButton(text="Показать все", callback_data='show_all')]
]

main_kb = ReplyKeyboardMarkup(keyboard=main_b, resize_keyboard=True)
verification_kb = InlineKeyboardMarkup(inline_keyboard=verification_b)
faq_kb = InlineKeyboardMarkup(inline_keyboard=faq_b)
notifications_kb = InlineKeyboardMarkup(inline_keyboard=notifications_b)
temp_departments = []
temp_groups = []

# Start command handler
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer("Привет! Это информационная система для института. Пожалуйста, выберите опцию.",
                         reply_markup=main_kb)

# Verification process
@dp.message(F.text == "Верификация")
async def process_verification(message: types.Message):
    await message.answer("Для доступа к функциям, пожалуйста, пройдите верификацию.", reply_markup=verification_kb)

# в будущем изменить
@dp.callback_query(F.data == "fill_form")
async def fill_form(callback_query: types.CallbackQuery, state: FSMContext):
    global temp_departments
    await state.set_state(Form.department)
    update_token()
    response = requests.get(department_url, headers=headers)
    # Проверяем успешность запроса
    if response.status_code == 200:
        data = response.json()
        temp_departments=[item['department_name'] for item in data]
        department_kb = await get_department_kb(temp_departments)
        await bot.send_message(callback_query.from_user.id, "Пожалуйста, выберите ваш факультет:", reply_markup=department_kb)
    else:
        await bot.send_message(callback_query.from_user.id, "Пожалуйста, выберите ваш факультет:")

@dp.callback_query(F.data.startswith("choose_department"))
async def process_group(callback_query: types.CallbackQuery, state: FSMContext):
    global temp_groups
    department_id = callback_query.data.replace("choose_department","")
    department = temp_departments[int(department_id)]
    await state.update_data(department=department)
    await state.set_state(Form.group)
    update_token()
    response = requests.get(groups_url, headers=headers)
    # Проверяем успешность запроса
    if response.status_code == 200:
        data = response.json()
        needed_groups = [group for group in data if group['department'] == department]
        temp_groups = [item['short_name'] for item in data]
        groups_kb = await get_groups_kb(temp_groups)
        await bot.send_message(callback_query.from_user.id, "Пожалуйста, выберите вашу группу:",
                               reply_markup=groups_kb)
    else:
        await bot.send_message(callback_query.from_user.id, "Пожалуйста, выберите вашу группу:")

@dp.callback_query(F.data.startswith("choose_group"))
async def process_group(callback_query: types.CallbackQuery, state: FSMContext):
    group_id = callback_query.data.replace("choose_group", "")
    group = temp_groups[int(group_id)]
    await state.update_data(group=group)
    await state.set_state(Form.name)
    await bot.send_message(callback_query.from_user.id, "Пожалуйста, введите ваше ФИО:")

@dp.message(Form.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Form.student_id)
    await message.answer("Пожалуйста, отправьте фотографию вашего студенческого билета:")

@dp.message(Form.student_id, F.photo)
async def process_student_id(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    group = user_data['group']
    name = user_data['name']
    student_id_photo = message.photo[-1].file_id
    # Send the data to the admin panel for verification
    # This is just a placeholder for the actual implementation
    await message.answer(f"Заявка отправлена на рассмотрение.\nГруппа: {group}\nФИО: {name}\n Фото: {student_id_photo}")
    await state.clear()

# FAQ process
@dp.message(F.text == "FAQ")
async def process_faq(message: types.Message):
    await message.answer("Выберите опцию:", reply_markup=faq_kb)

@dp.callback_query(F.data == "view_all")
async def view_all(callback_query: types.CallbackQuery):
    # Выполняем GET запрос к API с заголовком авторизации
    response = requests.get(faq_url, headers=headers)
    # Проверяем успешность запроса
    if response.status_code == 200:
        data = response.json()
        faqs = "\n\n".join([f"Вопрос: {item['question']}\nОтвет: {item['answer']}" for item in data])
        await bot.send_message(callback_query.from_user.id, f"Список всех вопросов и ответов:\n{faqs}")
    else:
        await bot.send_message(callback_query.from_user.id, f"Ошибка при запросе: {response.status_code} - {response.text}")

@dp.callback_query(F.data == "request")
async def request_faq(callback_query: types.CallbackQuery):
    await bot.send_message(callback_query.from_user.id, "Введите ваш запрос:")

@dp.message(default_state)
async def search_faq(message: types.Message):
    query = message.text
    # Выполняем GET запрос к API с заголовком авторизации
    update_token()
    response = requests.get(faq_url, headers=headers)
    # Проверяем успешность запроса
    if response.status_code == 200:
        data = response.json()
        results = faq_helper.search_faq(query, data)[:5]  # Call the search_faq function with the pack
        if results:
            await message.answer(f"Результаты поиска для запроса '{query}':")
            for result in results:
                await message.answer(f"Вопрос: {result['question']}\nОтвет: {result['answer']}")
        else:
            await message.answer(f"Не найдено результатов для запроса '{query}'.")
    else:
        await message.answer(f"Ошибка при запросе: {response.status_code} - {response.text}")

async def get_department_kb(departments):
    department_kb = InlineKeyboardMarkup(
        inline_keyboard=[
                            [InlineKeyboardButton(text=department, callback_data="choose_department" + str(i)) for
                             department in departments[i:i + 1]]
                            for i in range(0, len(departments), 1)
                        ]
    )
    return department_kb

async def get_groups_kb(groups):
    groups_kb = InlineKeyboardMarkup(
        inline_keyboard=[
                            [InlineKeyboardButton(text=group, callback_data="choose_group" + str(i)) for group in
                             groups[i:i + 1]]
                            for i in range(0, len(groups), 1)
                        ]
    )
    return groups_kb


# Notifications process
@dp.message(F.text == "Уведомления")
async def process_notifications(message: types.Message):
    await message.answer("Выберите опцию:", reply_markup=notifications_kb)

@dp.callback_query(F.data == "show_unread")
async def show_unread(callback_query: types.CallbackQuery):
    # Fetch and display unread notifications
    await bot.send_message(callback_query.from_user.id, "Непрочитанные уведомления...")

@dp.callback_query(F.data == "show_all")
async def show_all(callback_query: types.CallbackQuery):
    # Fetch and display all notifications
    await bot.send_message(callback_query.from_user.id, "Все уведомления...")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
