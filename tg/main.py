import asyncio
import logging
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.filters import Command, Filter, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup, default_state
from aiogram.fsm.storage.memory import MemoryStorage
from datetime import datetime
from config_reader import config

logging.basicConfig(level=logging.INFO)

form_router = Router()
bot = Bot(token=config.bot_token.get_secret_value())
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# States
class Form(StatesGroup):
    group = State()
    name = State()
    student_id = State()


groups = ["ПрИ-101", "ПрИ-201", "ПрИ-301", "ПрИ-401",
          "ПИ-101", "ПИ-201", "ПИ-301", "ПИ-401",
          "БИ-101", "БИ-201", "БИ-301", "БИ-401",
          "ПрИ-102", "ПрИ-103", "ПрИ-202", "ПрИ-203",
          "ПИ-102", "ПИ-103", "ПИ-202", "ПИ-203",
          "БИ-102", "БИ-103", "БИ-202", "БИ-203"]
with open('groups.txt', 'r', encoding='utf-8') as f:
    groups = [line.strip() for line in f.readlines()]

# Keyboards
main_b = [
    [KeyboardButton(text="Верификация")],
    [KeyboardButton(text="FAQ")]
]
verification_b = [
    [InlineKeyboardButton(text="Заполнить форму", callback_data='fill_form')]
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
groups_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=group, callback_data=group) for group in groups[i:i+3]]
        for i in range(0, len(groups), 3)
    ]
)


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
    await state.set_state(Form.group)
    await bot.send_message(callback_query.from_user.id, "Пожалуйста, выберите вашу группу:", reply_markup=groups_kb)


@dp.callback_query()
async def process_group(callback_query: types.CallbackQuery, state: FSMContext):
    group = callback_query.data
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
    # Fetch and display all FAQs
    await bot.send_message(callback_query.from_user.id, "Список всех вопросов и ответов...")


@dp.callback_query(F.data == "request")
async def request_faq(callback_query: types.CallbackQuery):
    await bot.send_message(callback_query.from_user.id, "Введите ваш запрос:")


@dp.message(default_state)
async def search_faq(message: types.Message):
    query = message.text
    # Search FAQs by query
    await message.answer(f"Результаты поиска для запроса '{query}': ...")


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
