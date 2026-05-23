import os
import re
import asyncio
from dotenv import load_dotenv
import django

# Initialize Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from feedback.models import Application, Message as DBMessage

load_dotenv()

# Settings
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN") or BOT_TOKEN
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
ADMIN_ID = os.getenv("ADMIN_ID")
WEBAPP_URL = os.getenv("WEBAPP_URL")

# Generate cache-busted URL to force Telegram to clear local webview cache
webapp_url = WEBAPP_URL or ""
if webapp_url:
    if not webapp_url.endswith("/") and "?" not in webapp_url:
        webapp_url = webapp_url + "/"
    WEBAPP_URL_CACHE_BUSTER = f"{webapp_url}?v=10" if "?" not in webapp_url else f"{webapp_url}&v=10"
else:
    WEBAPP_URL_CACHE_BUSTER = ""

# Initialize Bots
main_bot = Bot(token=BOT_TOKEN)
admin_bot = Bot(token=ADMIN_BOT_TOKEN) if ADMIN_BOT_TOKEN else None

dp = Dispatcher()

# 1. Start command in PM
@dp.message(Command("start"), F.chat.type == "private")
async def start(message: types.Message):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Murojaat qoldirish", web_app=WebAppInfo(url=WEBAPP_URL_CACHE_BUSTER))]
    ])
    await message.answer(
        "Salom! Pastdagi tugmani bosing va murojaat qoldiring yoki savol bering.", 
        reply_markup=markup
    )

# 2. Handler for admin reply in the admin group
# It listens to ADMIN_CHAT_ID for replies
from asgiref.sync import sync_to_async

@sync_to_async
def process_admin_reply_db(ticket_id, admin_text):
    try:
        application = Application.objects.get(id=ticket_id)
        
        # Sync chat history JSON
        from django.utils import timezone
        now_time = timezone.localtime().strftime("%H:%M")
        new_message = {"role": "admin", "text": admin_text, "time": now_time}
        
        history = list(application.chat_history) if application.chat_history else []
        history.append(new_message)
        application.chat_history = history
        
        application.is_answered = True
        application.save()
        
        # Create DB Message record
        DBMessage.objects.create(
            application=application,
            text=admin_text,
            is_from_admin=True
        )
        return application.user_id
    except Application.DoesNotExist:
        return None

if ADMIN_CHAT_ID:
    try:
        ADMIN_CHAT_ID_INT = int(ADMIN_CHAT_ID)
    except ValueError:
        ADMIN_CHAT_ID_INT = 0

    @dp.message(F.chat.id == ADMIN_CHAT_ID_INT, F.reply_to_message)
    async def handle_admin_reply_to_user(message: types.Message):
        reply = message.reply_to_message
        
        # Regex to extract ticket ID: "YANGI SHIKOYAT #123"
        match = re.search(r"YANGI SHIKOYAT #(\d+)", reply.text or reply.caption or "")
        if not match:
            return
            
        ticket_id = int(match.group(1))
        admin_text = message.text
        
        try:
            # Execute DB query safely in synchronous context
            user_id = await process_admin_reply_db(ticket_id, admin_text)
            
            if not user_id:
                await message.reply("❌ Xatolik: Bu ariza ID bazada topilmadi.")
                return
                
            # React with 🔥 on the admin message to show success (message is automatically sent via Django model's save method)
            await message.react([{"type": "emoji", "emoji": "🔥"}])
            
            
        except Exception as e:
            await message.reply(f"❌ Xatolik: {str(e)}")
            


# 3. Fallback PM reply handler for direct messages from admin
if ADMIN_ID:
    try:
        ADMIN_ID_INT = int(ADMIN_ID)
    except ValueError:
        ADMIN_ID_INT = 0

    @dp.message(F.chat.type == "private", F.reply_to_message, F.from_user.id == ADMIN_ID_INT)
    async def handle_direct_admin_reply(message: types.Message):
        original_text = message.reply_to_message.text or message.reply_to_message.caption
        if not original_text:
            return
            
        match = re.search(r"User:\s*(\d+)", original_text)
        if match:
            target_user_id = int(match.group(1))
            try:
                await main_bot.send_message(
                    chat_id=target_user_id,
                    text=f"✉️ <b>Qo'llab-quvvatlash xizmatidan javob:</b>\n\n{message.text}",
                    parse_mode="HTML"
                )
                await message.answer("✅ Javob foydalanuvchiga yuborildi!")
            except Exception as e:
                await message.answer(f"❌ Xatolik: Foydalanuvchi botni bloklagan bo'лишi mumkin.\n\n{e}")

async def main():
    print("Bots are starting...")
    
    # Programmatically set the Web App Menu Button to the cache-busted URL
    if WEBAPP_URL_CACHE_BUSTER:
        try:
            from aiogram.types import MenuButtonWebApp, WebAppInfo
            await main_bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Murojat",
                    web_app=WebAppInfo(url=WEBAPP_URL_CACHE_BUSTER)
                )
            )
            print(f"Successfully programmatically set Menu Button to: {WEBAPP_URL_CACHE_BUSTER}")
        except Exception as e:
            print(f"Failed to programmatically set Menu Button: {e}")

    active_bots = [main_bot]
    if admin_bot and admin_bot.token != main_bot.token:
        active_bots.append(admin_bot)
        print("Polling both Sumire Bot and Admin Group Bot...")
    else:
        print("Polling Sumire Bot...")

    await dp.start_polling(*active_bots)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bots stopped.")