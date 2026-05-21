import json
import os
import re
from urllib.parse import urljoin

from openai import OpenAI
import requests
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import Application, Message, Profile


DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

client = None
if DEEPSEEK_API_KEY:
    client = OpenAI(
        api_key=DEEPSEEK_API_KEY.strip(),
        base_url="https://api.deepseek.com/v1"
    )

SEARCH_BASE_URL = "https://bot.kawaii.uz"

ALLOWED_EMOTIONS = {
    "canthelp", "face palm", "fuu", "hmmm", "resolve or good",
    "shocked", "shy", "talking", "think", "ty", "waiting", "what",
}

THANKS_WORDS = ("rahmat", "raxmat", "tashakkur", "thanks", "thank you", "thx", "ty", "arigato")
COMPLIMENT_WORDS = ("chiroylisan", "yoqimtoy", "yaxshisan", "sevaman", "love")
RESOLVED_WORDS = ("ishladi", "hal boldi", "hal bo'ldi", "tuzaldi", "hammasi ishlayapti")


# === УСОВЕРШЕНСТВОВАННЫЙ ПРОМПТ С ФИЛЬТРАМИ ===
INTENT_PROMPT = """
Sen — Sumire, 15 yoshli yuqori sinf o'quvchisi, oy ruhi va Kawaii platformasida servis xodimisan.

=== TIL QOIDASI ===
Faqat o'zbek tilida, lotin alifbosida yozasan. 

=== JANRLAR RO'YXATI ===
Jangari, Sarguzasht, Komediya, Drama, Fantaziya, Pazandachilik, Dahshatli, Sirli, Romantika, Ilmiy-fantastika, Kundalik hayot, Sport, G'ayritabiiy, Hayajonli, Kattalar hayoti, Antropomorfik, Bezorilar, Detektiv, Ta'limiy, Oila, Shafqatsiz, Garem, Xatarli o'yin, Tarixiy, O'zga dunyo, Jang san'atlari, Robotlar, Tibbiyot, Harbiy, Musiqa, Mifologiya, Uyushgan jinoyatchilik, Otaku madaniyati, Parodiya, Sahna san'ati, Uy hayvonlari, Psixologik, Poyga, Reinkarnatsiya, Samuray, Maktab, Shou-biznes, Koinot, Strategik o'yin, G'ayritabiiy kuch, Omon qolish, Vaqt bo'ylab sayohat, Vampir, Video o'yinlar, Josey, Bolalar uchun, Syonen, Shojo, Shonen, O'yin.

=== JSON FORMATI VA VAZIFANG ===
{
  "intent": "search|ticket|chat|reject",
  "reply": "Javob matning. MATN ICHIGA HECH QANDAY LINK YOKI HAVOLA YOZMA!",
  "emotion": "talking|fuu|resolve or good|shocked|face palm|shy",
  "search_query": "aniq anime nomi YOKI tepadagi ro'yxatdan janr",
  "anime_type": "film|serial|bosh",
  "limit": 3,
  "offset": 0,
  "ticket_subject": "shikoyat mavzusi"
}

=== QIDIRUV VA FILTR QOIDALARI ===
1. EMOTSIYANI JANRGA O'GIRISH: Agar foydalanuvchi "yeg'latadigan", "qayg'uli", "sad" desa -> search_query: "Drama" bo'lsin. "kulgili", "rofl" desa -> search_query: "Komediya".
2. KINO YOKI SERIAL (anime_type): Agar alohida "film", "kino", "kino qilib", "to'liq metrajli" deb so'rasa -> anime_type: "film" bo'ladi. Agar "serial" so'rasa -> anime_type: "serial" bo'ladi. Aks holda "bosh" (bo'sh) qoldir.
3. LIMIT: Aytilmasa har doim 3 ta. 10 tadan ko'p so'rasa limit: 10 qil va "Miyam kompyuter emas..." deb ayt.
4. OFFSET: "yana", "boshqa", "davomi" desa, oldingi qidiruvdagi offset ni oshir. Yangi qidiruvda offset doim 0 bo'ladi.

=== EMOTSIYA VA INTENT QOIDALARI ===
1. Hentai, porno, nsfw (18+) so'ralsa -> intent: "reject", emotion: "fuu", qattiq rad et.
2. Sayt ishlamayapti, xato, bug, muammo bo'lsa -> intent: "ticket", emotion: "shocked".
3. Anime/Janr qidirsa -> intent: "search", emotion: "talking".
"""


def _sumire_response(text, emotion="talking", ticket_created=False, buttons=None, status=200):
    response_data = {
        "role": "sumire",
        "text": text,
        "emotion": emotion if emotion in ALLOWED_EMOTIONS else "talking",
        "ticket_created": ticket_created,
    }
    
    if buttons:
        response_data["buttons"] = buttons
        
    return JsonResponse(response_data, status=status)

def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def _normalize_search_item(item):
    if not isinstance(item, dict): 
        return item

    title = item.get("title_uzb") or item.get("title_org") or "Nomalum anime"
    hash_id = item.get("hash_id")
    url = f"https://bot.kawaii.uz/anime/{hash_id}/" if hash_id else "#"

    normalized = {
        "title": str(title),
        "url": url,
        "episodes": item.get("episode_kawaii"),
        "year": item.get("year"),
        "type": item.get("type_uzb", "")
    }

    return normalized

def search_manga_database(query: str, limit: int = 3, offset: int = 0, anime_type: str = ""):
    try:
        response = requests.get(
            f"{SEARCH_BASE_URL}/api/v1/search/",
            params={"q": query, "limit": 50}, 
            timeout=5,
        )
        if response.status_code != 200:
            return []
            
        response_json = response.json()
        results_data = response_json.get("data", [])
        
        if not isinstance(results_data, list):
            return []
            
        normalized_results = [_normalize_search_item(item) for item in results_data]
        
        # --- ФИЛЬТРАЦИЯ ПО ТИПУ (КИНО ИЛИ СЕРИАЛ) ---
        anime_type = anime_type.lower()
        if anime_type == "film":
            # Ищем слова film, kino, movie в type_uzb
            normalized_results = [
                r for r in normalized_results 
                if r.get("type") and any(k in str(r["type"]).lower() for k in ["film", "kino", "movie"])
            ]
        elif anime_type == "serial":
            normalized_results = [
                r for r in normalized_results 
                if r.get("type") and "serial" in str(r["type"]).lower()
            ]

        # Отрезаем нужный кусок (пагинация)
        return normalized_results[offset : offset + limit]
        
    except Exception as e:
        print(f"Database search error: {e}")
        return []

def _format_search_results(results):
    if not results:
        return "*(Bazada hech narsa topilmadi...)*", None
    
    lines = []
    buttons = []
    
    for item in results:
        title = item.get('title', 'Nomalum')
        url = item.get('url', '#')
        
        details = []
        if item.get("year"): 
            details.append(str(item["year"]))
        # Добавляем тип аниме (Фильм или кол-во серий)
        if item.get("type"):
            type_str = str(item["type"]).lower()
            if "film" in type_str or "kino" in type_str:
                details.append("Film")
            elif item.get("episodes"): 
                details.append(f"{item['episodes']} qism")
        
        suffix = f" ({', '.join(details)})" if details else ""
        lines.append(f"📺 <b>{title}</b>{suffix}")
        
        buttons.append({
            "text": f"▶️ Ko'rish", 
            "url": url
        })
        
    return "\n\n".join(lines), buttons

def _contains_any(text, words):
    return any(word in text for word in words)

def _is_greeting(text):
    clean_text = re.sub(r'[^a-z]', '', text.lower())
    patterns = [r'^s+a+l+o+m+$', r'^s+l+m+$', r'^q+a+l+e+$', r'^h+i+$']
    return any(re.match(p, clean_text) for p in patterns)

def _notify_admins(application):
    token = os.getenv("BOT_TOKEN")
    if not token: return
    message_text = (
        f"<b>Yangi murojaat (#{application.id})</b>\n"
        f"<b>Mavzu:</b> {application.subject}\n"
        f"{application.chat_history[-1].get('text', '') if application.chat_history else ''}"
    )
    admin_ids = Profile.objects.filter(user__is_staff=True).values_list("telegram_id", flat=True)
    for telegram_id in admin_ids:
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": telegram_id, "text": message_text, "parse_mode": "HTML"},
                timeout=5,
            )
        except Exception:
            pass

def _create_ticket(user_text, user_id=None, username=None, subject=None):
    subject = (subject or "Web App murojaati").strip()[:50]
    now = timezone.localtime().strftime("%H:%M")

    application = Application.objects.create(
        user_id=_safe_int(user_id) if user_id else 0,
        username=username or "",
        category="report",
        subject=subject,
        chat_history=[{"role": "user", "text": user_text, "time": now}],
    )
    Message.objects.create(application=application, text=user_text, is_from_admin=False)
    _notify_admins(application)
    return application

def _route_without_ai(user_text):
    text_lower = user_text.lower().strip()
    if not text_lower:
        return _sumire_response("Iltimos, matn kiriting. *uzoqqa qaraydi*", "what", status=400)
    if re.search(r'[А-Яа-я]', user_text):
        return _sumire_response("Kechirasiz, men kirill alifbosini tushunmayman. Faqat lotin yozuvida yozing. *yuzini burib oladi*", "face palm")
    if _is_greeting(text_lower):
        return _sumire_response("Salom. Qanday yordam kerak? *qiziqishsiz qaraydi*", "talking")
    if _contains_any(text_lower, THANKS_WORDS):
        return _sumire_response("Arzimaydi. Yana ishing tushsa yozarsan. *yengil bosh irg'aydi*", "ty")
    if _contains_any(text_lower, COMPLIMENT_WORDS):
        return _sumire_response("G'alati gaplarni yozishni bas qil... *yuzini burib qizaradi*", "shy")
    if _contains_any(text_lower, RESOLVED_WORDS):
        return _sumire_response("Yaxshi. Muammo hal bo'lgan bo'lsa, ishimni davom ettiraman. *xotirjam nafas oladi*", "resolve or good")
    return None

def _parse_ai_command(user_text, chat_history_text=""):
    if not client:
        return {"intent": "chat", "reply": "Ulanishda muammo bor... *kompyuterga uradi*", "emotion": "shocked"}

    full_prompt = f"--- OLDINGI KONTEKST ---\n{chat_history_text}\n\n--- YANGI XABAR ---\nUser: {user_text}" if chat_history_text else f"User: {user_text}"

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": INTENT_PROMPT},
            {"role": "user", "content": full_prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.1, 
    )

    try:
        return json.loads(response.choices[0].message.content)
    except Exception:
        return {"intent": "chat", "reply": "Miyam og'rib ketdi... *peshonasini ushlaydi*", "emotion": "face palm"}

def _execute_ai_command(command, user_text, user_id=None, username=None):
    intent = command.get("intent", "chat")
    emotion = command.get("emotion", "talking")
    reply = command.get("reply", "Nima deyishni ham bilmayman...").strip()

    if intent == "search":
        query = command.get("search_query", "")
        anime_type = command.get("anime_type", "")
        limit = min(max(_safe_int(command.get("limit"), 3), 1), 10)
        offset = _safe_int(command.get("offset"), 0)
        
        results = search_manga_database(query, limit=limit, offset=offset, anime_type=anime_type)
        
        if not results and offset > 0:
            return _sumire_response("Boshqa topa olmadim. Shu janrda yoki nomda boshqa anime qolmagan ko'rinadi... *boshini qashlaydi*", "face palm")
            
        formatted_text, buttons = _format_search_results(results)
        final_text = f"{reply}\n\n{formatted_text}"
        
        return _sumire_response(final_text, emotion, buttons=buttons)

    if intent == "ticket":
        subject = command.get("ticket_subject") or "Web App muammo"
        app = _create_ticket(user_text, user_id=user_id, username=username, subject=subject)
        return _sumire_response(f"{reply}\n\n(ID: #{app.id} - Murojaat adminlarga yuborildi)", emotion, ticket_created=True)

    return _sumire_response(reply, emotion)

@csrf_exempt
def api_send_message(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
        user_text = (data.get("text") or "").strip()
        user_id = data.get("user_id")
        username = data.get("username") or data.get("first_name") or ""

        direct_response = _route_without_ai(user_text)
        if direct_response:
            return direct_response

        user_ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0] or request.META.get("REMOTE_ADDR", "unknown")
        user_daily_key = f"user_limit_{user_ip}"
        user_requests = cache.get(user_daily_key, 0)
        
        if user_requests >= 30:
            return _sumire_response("Bugun judayam ko'p savol berding. Charchadim. Ertaga kel... *ko'zlarini yopadi*", "fuu")

        history_key = f"chat_history_{user_ip}"
        chat_history = cache.get(history_key, [])
        history_text = "\n".join([f"{msg['role']}: {msg['text']}" for msg in chat_history])

        command = _parse_ai_command(user_text, history_text)
        cache.set(user_daily_key, user_requests + 1, timeout=86400)
        
        ai_response = _execute_ai_command(command, user_text, user_id=user_id, username=username)

        try:
            reply_data = json.loads(ai_response.content.decode('utf-8'))
            reply_text = reply_data.get("text", "")
            
            chat_history.append({"role": "User", "text": user_text})
            chat_history.append({"role": "Sumire", "text": reply_text})
            cache.set(history_key, chat_history[-6:], timeout=3600)
        except Exception as e:
            print(f"History cache error: {e}")

        return ai_response

    except Exception as exc:
        print(f"API Error: {str(exc)}")
        return _sumire_response("Tizimda xatolik yuz berdi... Miyam qotib qoldi. *boshini ushlaydi*", "canthelp", status=500)