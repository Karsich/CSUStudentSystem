import asyncio
import logging
import requests
from fastapi import FastAPI
from fastapi.responses import Response

import faq_helper
import logging
from aiogram.client.default import DefaultBotProperties
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, Update
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
import uvicorn
from faq_helper import search_faq
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup, default_state
from config import BOT_TOKEN, NGROK_TUNNEL_URL
from contextlib import asynccontextmanager

API_TOKEN = BOT_TOKEN

# URL вашего ngrok
WEBHOOK_HOST = NGROK_TUNNEL_URL
WEBHOOK_PATH = '/webhook'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
WEBHOOKO_URL = f"{WEBHOOK_HOST}/bot/{API_TOKEN}"

# Настройки веб-сервера
WEBAPP_HOST = 'localhost'
WEBAPP_PORT = 5000

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN,
          default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

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

# States
class Form(StatesGroup):
    group = State()
    name = State()
    department = State()
    student_id = State()

#with open('groups.txt', 'r', encoding='utf-8') as f:
#    groups = sorted([line.strip() for line in f.readlines()])

# Keyboards
main_b = [
    [InlineKeyboardButton(text="Подать заявку в группу",callback_data='fill_form')],
    [InlineKeyboardButton(text="FAQ",callback_data='FAQ')]
]
verification_b = [
    [InlineKeyboardButton(text="Верификация", callback_data='fill_form')]
]
faq_b = [
    #[InlineKeyboardButton(text="Просмотр всех вопросов", callback_data='view_all')],
    [InlineKeyboardButton(text="Запрос", callback_data='request')]
]
notifications_b = [
    [InlineKeyboardButton(text="Показать непрочтенные", callback_data='show_unread')],
    [InlineKeyboardButton(text="Показать все", callback_data='show_all')]
]

main_kb = InlineKeyboardMarkup(inline_keyboard=main_b)
verification_kb = InlineKeyboardMarkup(inline_keyboard=verification_b)
faq_kb = InlineKeyboardMarkup(inline_keyboard=faq_b)
notifications_kb = InlineKeyboardMarkup(inline_keyboard=notifications_b)
temp_departments = []
temp_groups = []

# Start command handler
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    response = requests.get(f'http://95.174.92.220:8000/students/{message.from_user.id}', headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data:
            await message.answer("Привет! Это информационная система для института. Пожалуйста, выберите опцию.",
                                 reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Уведомления")]], resize_keyboard=True))
        else:
            await message.answer("Привет! Это информационная система для института. Пожалуйста, выберите опцию.",
                                 reply_markup=main_kb)
    elif response.status_code == 403:
        await message.answer("Привет! Это информационная система для института. Пожалуйста, выберите опцию.",
                             reply_markup=main_kb)
    else:
        await message.answer("Ошибка при запросе: " + str(response.status_code) + " - " + response.text)

# Verification process
#@dp.message(F.text == "Верификация")
#async def process_verification(message: types.Message):
#    await message.answer("Для доступа к функциям, пожалуйста, пройдите верификацию.", reply_markup=verification_kb)

# в будущем изменить
@dp.callback_query(F.data == "fill_form")
async def fill_form(callback_query: types.CallbackQuery, state: FSMContext):
    await state.set_state(Form.group)
    update_token()
    response = requests.get(groups_url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        groups = [item['short_name'] for item in data]
        groups_kb = await get_groups_kb(groups)
        await bot.send_message(callback_query.from_user.id, "Выберите группу:", reply_markup=groups_kb)
    else:
        await bot.send_message(callback_query.from_user.id, "Ошибка при запросе: " + str(response.status_code) + " - " + response.text)

@dp.callback_query(F.data.startswith("choose_group"))
async def process_group(callback_query: types.CallbackQuery, state: FSMContext):
    group = callback_query.data.replace("choose_group", "")
    response = requests.get(f"{groups_url}/{group}", headers=headers)
    if response.status_code == 200:
        data = response.json()
        department = data['department']
        specialty = data['specialty']
        members_count = data['user_count']
        await bot.send_message(callback_query.from_user.id, f"Группа: {group}\nДепартамент: {department}\nСпециальность: {specialty}\nКоличество участников: {members_count}")
        join_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data=f"join_group{group}")],
            [InlineKeyboardButton(text="Нет", callback_data="fill_form")]
        ])
        await bot.send_message(callback_query.from_user.id, "Хотите присоединиться к этой группе?", reply_markup=join_kb)
    else:
        await bot.send_message(callback_query.from_user.id, "Ошибка при запросе: " + str(response.status_code) + " - " + response.text)

@dp.callback_query(F.data.startswith("join_group"))
async def join_group(callback_query: types.CallbackQuery, state: FSMContext):
    # Send the data to the admin panel for verification
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
    student_id_photo = message.photo[-1].file_id
    tg_chat = message.chat.id

    # Send the data to the admin panel for verification
    ticket_data = {
        'type_ticket': 'verification',
        'tgchat_id': tg_chat,
        'wish_group': group,
        'fullname': name,
        #    'photo': student_id_photo
    }
    update_token()
    response = requests.post('http://95.174.92.220:8000/tickets', json=ticket_data)

    if response.status_code == 200:
        response_trust = requests.get(f'http://95.174.92.220:8000/tickets/{tg_chat}/active')
        dataa = response_trust.json()
        if response_trust.status_code == 200 & dataa:
            await message.answer("Заявка была отправлена ранее")
        else:
            await message.answer(f"Заявка отправлена на рассмотрение.\nГруппа: {group}\nФИО: {name}\n Фото: {student_id_photo}")
    else:
        await message.answer("Ошибка отправки заявки. Пожалуйста, повторите попытку.")

    await state.clear()

# FAQ process
@dp.callback_query(F.data == "FAQ")
async def process_faq(callback_query: types.CallbackQuery):
    await bot.send_message(callback_query.from_user.id, "Выберите опцию:", reply_markup=faq_kb)

#@dp.callback_query(F.data == "view_all")
#async def view_all(callback_query: types.CallbackQuery):
    # Выполняем GET запрос к API с заголовком авторизации
    #    response = requests.get(faq_url, headers=headers)
    # Проверяем успешность запроса
    #    if response.status_code == 200:
    #        data = response.json()
    #        faqs = "\n\n".join([f"Вопрос: {item['question']}\nОтвет: {item['answer']}" for item in data])
    #       await bot.send_message(callback_query.from_user.id, f"Список всех вопросов и ответов:\n{faqs}")
    #   else:
#        await bot.send_message(callback_query.from_user.id, f"Ошибка при запросе: {response.status_code} - {response.text}")

@dp.callback_query(F.data == "request")
async def request_faq(callback_query: types.CallbackQuery):
    await bot.send_message(callback_query.from_user.id, "Введите ваш запрос:")

@dp.message(default_state)
async def search_faq(message: types.Message):
    query = message.text
    faq_data = {
        'message': query
    }
    # Выполняем GET запрос к API с заголовком авторизации
    update_token()
    response = requests.post('http://95.174.92.220:8000/faqs/search', json=faq_data)
    # Проверяем успешность запроса
    if response.status_code == 200:
        data = response.json()
        for result in data:
             await message.answer(f"Вопрос: {result['question']}\nОтвет: {result['answer']}")
        #results = faq_helper.search_faq(query, data)[:5]  # Call the search_faq function with the pack
        #if results:
        #    await message.answer(f"Результаты поиска для запроса '{query}':")
        #    for result in results:
        #        await message.answer(f"Вопрос: {result['question']}\nОтвет: {result['answer']}")
        #else:
        #    await message.answer(f"Не найдено результатов для запроса '{query}'.")
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
                            [InlineKeyboardButton(text=group, callback_data="choose_group" + group) for group in
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    await bot.set_webhook(url=WEBHOOK_URL,
                          allowed_updates=dp.resolve_used_update_types(),
                          drop_pending_updates=True)
    yield
    await bot.delete_webhook()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@dp.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer('Привет!')


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

async def main():
    await bot.delete_webhook()
    await dp.start_polling(bot)
@app.post("/webhook")
async def webhook(request: Request) -> None:
    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)


if __name__ == "__main__":
    asyncio.run(main())