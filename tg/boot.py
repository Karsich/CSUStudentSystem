from aiogram import Bot, Dispatcher, types
from aiogram.utils.executor import start_webhook
import logging
from config import BOT_TOKEN, NGROK_TUNNEL_URL

API_TOKEN = BOT_TOKEN

# URL вашего ngrok
WEBHOOK_HOST = NGROK_TUNNEL_URL
WEBHOOK_PATH = '/webhook'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Настройки веб-сервера
WEBAPP_HOST = 'localhost'
WEBAPP_PORT = 5000

# Включение логирования
logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply("Hello! I'm your bot!")

@dp.message_handler()
async def echo(message: types.Message):
    await message.answer(message.text)

async def on_startup(dp):
    logging.warning('Starting up..')
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(dp):
    logging.warning('Shutting down..')
    await bot.delete_webhook()
    await dp.storage.close()
    await dp.storage.wait_closed()
    logging.warning('Bye!')

if __name__ == '__main__':
    start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        host=WEBAPP_HOST,
        port=WEBAPP_PORT,
    )