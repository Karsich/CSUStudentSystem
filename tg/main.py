import asyncio
import logging
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup, default_state

from config import BOT_TOKEN, NGROK_TUNNEL_URL
from service import APIService

API_TOKEN = BOT_TOKEN

# URL вашего ngrok
WEBHOOK_HOST = NGROK_TUNNEL_URL
WEBHOOK_PATH = '/webhook'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Настройки веб-сервера
WEBAPP_HOST = 'localhost'
WEBAPP_PORT = 5000

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

login_url = 'http://95.174.92.220:8000/auth/login'
groups_url = 'http://95.174.92.220:8000/groups'
login_data = {
    "username": "telegram",
    "email": "telegram@telegram.com",
    "fullname": "none",
    "role": "system",
    "password": "awJwnbbT"
}

api_service = APIService(login_url, groups_url, login_data)

class Form(StatesGroup):
    group = State()
    name = State()
    student_id = State()
    question = State()
    add_photo = State()
    question_photo = State()

main_b = [
    [InlineKeyboardButton(text="Подать заявку в группу", callback_data='select_course')],
    [InlineKeyboardButton(text="FAQ", callback_data='FAQ')]
]
main_auth_b = [
    [InlineKeyboardButton(text="Задать вопрос администратору", callback_data='ask_admin')],
    [InlineKeyboardButton(text="FAQ", callback_data='FAQ')]
]

main_kb = InlineKeyboardMarkup(inline_keyboard=main_b)
main_auth_kb = InlineKeyboardMarkup(inline_keyboard=main_auth_b)

@dp.message(CommandStart())
async def send_welcome(message: types.Message):
    async with httpx.AsyncClient() as client:
        response = await client.get(f'http://95.174.92.220:8000/students/{message.from_user.id}', headers=api_service.headers)
        if response.status_code == 200:
            data = response.json()
            if data:
                await message.answer("Привет! Это информационная система для института. Пожалуйста, выберите опцию.",
                                     reply_markup=main_auth_kb)
            else:
                await message.answer("Привет! Это информационная система для института. Пожалуйста, выберите опцию.",
                                     reply_markup=main_kb)
        elif response.status_code == 403:
            await message.answer("Привет! Это информационная система для института. Пожалуйста, выберите опцию.",
                                 reply_markup=main_kb)
        else:
            await message.answer("Ошибка при запросе: " + str(response.status_code) + " - " + response.text)

@dp.callback_query(lambda c: c.data == "select_course")
async def select_course(callback_query: types.CallbackQuery):
    courses_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{i} курс", callback_data=f"choose_course_{i}")] for i in range(1, 6)
        ]
    )
    await bot.send_message(callback_query.from_user.id, "Выберите курс:", reply_markup=courses_kb)

@dp.callback_query(lambda c: c.data.startswith("choose_course"))
async def process_course(callback_query: types.CallbackQuery):
    course = int(callback_query.data.split("_")[-1])
    await api_service.update_token()
    groups = await api_service.get_groups()
    course_groups = [group for group in groups if group['short_name'].split('-')[-1].startswith(str(course))]
    groups_kb = await get_groups_kb([item['short_name'] for item in course_groups])
    await bot.send_message(callback_query.from_user.id, "Выберите группу:", reply_markup=groups_kb)

@dp.callback_query(lambda c: c.data.startswith("choose_group"))
async def process_group(callback_query: types.CallbackQuery, state: FSMContext):
    group = callback_query.data.replace("choose_group", "")
    data = await api_service.get_group_details(group)
    department = data['department']
    specialty = data['specialty']
    members_count = data['user_count']
    await bot.send_message(callback_query.from_user.id, f"Группа: {group}\nДепартамент: {department}\nСпециальность: {specialty}\nКоличество участников: {members_count}")
    join_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data=f"join_group{group}")],
        [InlineKeyboardButton(text="Нет", callback_data="select_course")]
    ])
    await bot.send_message(callback_query.from_user.id, "Хотите присоединиться к этой группе?", reply_markup=join_kb)

@dp.callback_query(lambda c: c.data.startswith("join_group"))
async def join_group(callback_query: types.CallbackQuery, state: FSMContext):
    await state.update_data(group=callback_query.data.replace("join_group", ""))
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
    student_id_photo = message.photo[-1]
    tg_chat = message.chat.id

    photo_file = await bot.get_file(student_id_photo.file_id)
    photo_url = f"https://api.telegram.org/file/bot{API_TOKEN}/{photo_file.file_path}"

    async with httpx.AsyncClient() as client:
        response = await client.get(photo_url)
        photo_bytes = response.content

    ticket_data = {
        'type_ticket': 'verification',
        'tgchat_id': tg_chat,
        'wish_group': group,
        'fullname': name,
    }
    response = await api_service.submit_ticket(ticket_data, photo_bytes, 'student_id.jpg')
    if response.status_code == 201:
        dataa = await api_service.check_active_ticket(tg_chat)
        if dataa:
            await message.answer("Заявка была отправлена ранее")
        else:
            await message.answer(f"Заявка отправлена на рассмотрение.\nГруппа: {group}\nФИО: {name}")
    else:
        await message.answer("Ошибка отправки заявки. Пожалуйста, повторите попытку.")

    await state.clear()

@dp.callback_query(lambda c: c.data == "FAQ")
async def process_faq(callback_query: types.CallbackQuery):
    await bot.send_message(callback_query.from_user.id, "Выберите опцию:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Ввести запрос", callback_data="request")]
    ]))

@dp.callback_query(lambda c: c.data == "request")
async def request_faq(callback_query: types.CallbackQuery):
    await bot.send_message(callback_query.from_user.id, "Введите ваш запрос:")

@dp.message(default_state)
async def search_faq(message: types.Message):
    query = message.text
    results = await api_service.search_faq(query)
    for result in results:
        await message.answer(f"Вопрос: {result['question']}\nОтвет: {result['answer']}")

@dp.callback_query(lambda c: c.data == "ask_admin")
async def ask_admin(callback_query: types.CallbackQuery, state: FSMContext):
    await state.set_state(Form.question)
    await bot.send_message(callback_query.from_user.id, "Введите ваш вопрос:")

@dp.message(Form.question)
async def process_question(message: types.Message, state: FSMContext):
    question = message.text
    await state.update_data(question=question)
    add_photo_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data="add_photo_yes")],
            [InlineKeyboardButton(text="Нет", callback_data="add_photo_no")]
        ]
    )
    await state.set_state(Form.add_photo)
    await message.answer("Хотите добавить фото к вашему вопросу?", reply_markup=add_photo_kb)

@dp.callback_query(lambda c: c.data == "add_photo_yes")
async def ask_for_photo(callback_query: types.CallbackQuery, state: FSMContext):
    await state.set_state(Form.question_photo)
    await bot.send_message(callback_query.from_user.id, "Пожалуйста, отправьте фото:")

@dp.callback_query(lambda c: c.data == "add_photo_no")
async def submit_question(callback_query: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    question = user_data['question']
    tg_chat = callback_query.from_user.id

    ticket_data = {
        'type_ticket': 'request',
        'tgchat_id': tg_chat,
        'message': question,
    }
    response = await api_service.submit_ticket(ticket_data)
    if response.status_code == 201:
        await bot.send_message(callback_query.from_user.id, "Ваш вопрос был отправлен.")
    else:
        await bot.send_message(callback_query.from_user.id, f"Ошибка отправки вопроса. Пожалуйста, повторите попытку. {response.content}")

    await state.clear()

@dp.message(Form.question_photo, F.photo)
async def process_question_photo(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    question = user_data['question']
    photo = message.photo[-1]
    tg_chat = message.chat.id

    photo_file = await bot.get_file(photo.file_id)
    photo_url = f"https://api.telegram.org/file/bot{API_TOKEN}/{photo_file.file_path}"

    async with httpx.AsyncClient() as client:
        response = await client.get(photo_url)
        photo_bytes = response.content

    ticket_data = {
        'type_ticket': 'request',
        'tgchat_id': 111123333333333,
        'message': question,
    }
    response = await api_service.submit_ticket(ticket_data, photo_bytes, 'question_photo.jpg')
    if response.status_code == 201:
        await message.answer("Ваш вопрос был отправлен.")
    else:
        await message.answer("Ошибка отправки вопроса. Пожалуйста, повторите попытку.")

    await state.clear()

async def get_groups_kb(groups):
    groups_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=group, callback_data="choose_group" + group)] for group in groups
        ]
    )
    return groups_kb

if __name__ == "__main__":
    dp.run_polling(bot)
