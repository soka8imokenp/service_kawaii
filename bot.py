import os
from dotenv import load_dotenv
import asyncio
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

load_dotenv()

# Настройки
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID")) # ID должен быть числом для aiogram
WEBAPP_URL = os.getenv("WEBAPP_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# 1. Команда /start для открытия Mini App
@dp.message(Command("start"))
async def start(message: types.Message):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Murojaat qoldirish", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    await message.answer(
        "Salom! Pastdagi tugmani bosing va murojaat qoldiring yoki savol bering.", 
        reply_markup=markup
    )

# 2. Обработчик твоих ответов (Reply)
@dp.message(F.reply_to_message)
async def handle_admin_reply(message: types.Message):
    # Проверяем, что отвечаешь именно ты
    if message.from_user.id == ADMIN_ID:
        
        # Берем текст из сообщения, на которое ты отвечаешь
        original_text = message.reply_to_message.text or message.reply_to_message.caption
        
        if original_text:
            # Ищем #id12345678 в тексте
            match = re.search(r"#id(\d+)", original_text)
            
            if match:
                target_user_id = match.group(1)
                try:
                    # Отправляем твой ответ пользователю
                    await bot.send_message(
                        chat_id=target_user_id,
                        text=f"✉️ <b>Qo'llab-quvvatlash xizmatidan javob:</b>\n\n{message.text}",
                        parse_mode="HTML"
                    )
                    await message.answer("✅ Javob foydalanuvchiga yuborildi!")
                except Exception as e:
                    await message.answer(f"❌ Xatolik: Foydalanuvchi botni bloklagan bo'lishi mumkin.\n\n{e}")
            else:
                # Если #id не найден, бот ничего не делает (чтобы не мешать обычному общению)
                pass

async def main():
    print("Bot ishga tushdi va ishlashga tayyor...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot o‘chirildi")