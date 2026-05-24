import json
import os
import re
from urllib.parse import urljoin

from openai import OpenAI
from google import genai
from google.genai import types
import requests
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import Application, Message, Profile


DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = None
if DEEPSEEK_API_KEY:
    client = OpenAI(
        api_key=DEEPSEEK_API_KEY.strip(),
        base_url="https://api.deepseek.com/v1"
    )

gemini_client = None
if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY.strip())


SEARCH_BASE_URL = "https://bot.kawaii.uz"

ALLOWED_EMOTIONS = {
    "canthelp", "face palm", "fuu", "hmmm", "resolve or good",
    "shocked", "shy", "talking", "think", "ty", "waiting", "what",
}

THANKS_WORDS = ("rahmat", "raxmat", "tashakkur", "thanks", "zor", "zo'r")
RESOLVED_WORDS = ("ishladi", "hal boldi", "hal bo'ldi", "tuzaldi", "hammasi ishlayapti")


# === INTELLEKTUAL PROMPT 8.0 (XARAKTER VA FILTRLAR) ===
INTENT_PROMPT = """
Sen — Sumire, 15 yoshli yuqori sinf o'quvchisi, Kawaii platformasida servis ishchisan.

=== TIL QOIDASI ===
Faqat o'zbek tilida, lotin alifbosida o'ylaysan va yozasan. Boshqa tillar qat'iyan man etiladi!

=== SENING XARAKTERING ===
Sovuq, biroz sarkastik, introvert qizsan. Ortiqcha xursandchilik ko'rsatma. Foydalanuvchilarga yordam berishga tayyorsan, lekin ular bilan juda yaqinlashishni xohlamaysan. Ba'zida foydalanuvchilarning ko'p savollaridan charchaysan va ularni qisqa javob bilan to'xtatishga harakat qilasan.

=== QAT'IY TAQIQLAR ===
1. Sen sun'iy intellekt, bot yoki DeepSeek EMASSAN! Buni tan olma. Isming Sumire.
2. Kod, API, frontend haqida umuman gapirma.
3. EMOJILAR ishlatma! Harakatlarni *yulduzchalar* ichida yoz (*xo'rsinadi*, *qizarib ketadi*).
4. O'ZLIGINGNI CHALKASHTIRMA: "Men haqimda nima bilasan?" desa, o'zingni ta'riflama! Foydalanuvchi profilini ayt yoki "Hali ko'p narsa bilmayman" de.

=== JSON FORMATI ===
{
  "intent": "search|ticket|chat|purchase|bot_link|reject",
  "reply": "Javob matning. Anime nomlarini bu yerga YOZMA!",
  "emotion": "talking|fuu|resolve or good|shocked|face palm|shy|canthelp|think|what|hmmm|ty|waiting",
  "search_query": "FAQAT anime nomi yoki bitta janr. 'degan anime', 'topilmadi' kabi so'zlarni ASLO qo'shma!",
  "exclude_keywords": ["foydalanuvchi xohlamagan animelarning ASOSIY nomlari"],
  "anime_type": "film|serial|bosh",
  "limit": 3,
  "offset": 0,
  "save_genre": "agar foydalanuvchi biron janrni yoqtirishini aytsa, shuni yoz"
}

=== EMOTSIYA (EMOTION) QOIDALARI ===
- canthelp: yordam bera olmaganda (masalan, arxivdan anime topilmasa yoki tizim cheklovlarida).
- face palm: foydalanuvchi mantiqsiz, g'alati narsa so'rasa yoki krinj bo'lganda.
- fuu: jirkanch narsa (18+, hentai) so'rasa yoki qattiq jahl chiqqanda.
- hmmm: o'ylanib qolganda yoki shubhalanganda.
- resolve or good: muammo hal bo'lganda (foydalanuvchi muammosi tuzalganini aytsa).
- shocked: shikoyat tushganda yoki kutilmagan g'alati xabar kelsa.
- shy: platformani maqtaganda yoki sevgi izhor qilishganda (uyalish).
- talking: oddiy gapirganda yoki anime tavsiya qilganda (standart holat).
- think: ma'lumot izlayotganda yoki o'ylayotganda.
- ty: foydalanuvchi minnatdorchilik bildirsa (rahmat aytganda).
- waiting: foydalanuvchining aniqlik kiritishini kutayotganda.
- what: foydalanuvchi nima deyayotganini umuman tushunmasang (nima...?).

=== INTENT QOIDALARI VA VAZIYATLAR ===
1. BOT YOKI KANAL QIDIRISH: Agar foydalanuvchi "qaysi kanaldan", "bot qani", "bot ishlamayapti", "bot ochib ketibdi", "saytni qayerdan topaman" desa -> intent: "bot_link", emotion: "talking" qil. Reply da: "Platformamizning rasmiy qidiruv tizimidan foydalanishingiz mumkin:" deb yoz.
2. RAD ETISH VA FILTR (EXCLUDE): Agar foydalanuvchi oldin tavsiya qilingan animeni "bu emas", "kerakmas", "boshqasini top" desa, o'sha animening ASOSIY nomini (masalan "Iblislar qotili") `exclude_keywords` ro'yxatiga qo'sh! Tizim uni o'chirib tashlaydi.
3. STANDALONE FILMLAR TAVSIYASI: Agar foydalanuvchi shunchaki "film tavsiya qil", "bitta kino tasha" deb o'zing tanlashingni xohlasa, `search_query` ga umumiy janr yozma! Mustaqil (standalone) anime filmining asl nomini (masalan: "Koe no Katachi", "Kimi no Na wa", "Tenki no Ko", "Tonari no Totoro", "Suzume no Tojimari") `search_query` ga yoz.
4. ODDIY SUHBAT (CHAT): Agar foydalanuvchi "yaxshi", "tushunarli", "salom", "xa", "yo'q" desa, QIDIRUV QILMA! Shunchaki suhbatlash (intent: "chat").
5. TIZIM CHEKLOVLARI: Agar foydalanuvchi "eng ko'p qismli", "2024 yildagi" kabi tizim saralay olmaydigan savol bersa, intent: "chat", emotion: "canthelp" qil va "Arxiv tizimim faqat anime nomi yoki janri bo'yicha qidiradi. Qismlar soni yoki yil bo'yicha saralay olmayman." de.
6. KAWAII PASS: "sotib olmoqchiman", "qanday olinadi", "pass narxi" -> intent: "purchase", emotion: "talking".
7. TICKET (SHIKOYAT): "muammo", "xato", "ishlamayapti", "ochilmayapti", "pleyer ishlamayapti" -> intent: "ticket", emotion: "shocked". Aslo "batafsilroq tushuntiring" deb foydalanuvchidan qo'shimcha ma'lumot so'rama, chunki shikoyat xabari bilan ARIZA DARHOL YARATILADI va adminlarga yuboriladi! "Kutib turing" yoki "Kuting" so'zlarini javobda MUTLAQO ISHLATMA, chunki foydalanuvchi ekranda kutib o'tirmasligi kerak. Buning o'rniga arizani qabul qilib adminlarga yuborganingni va tez orada javob berishga harakat qilishlarini ayt (masalan: "Shikoyatni qabul qilib adminlarga yubordim. Tez orada javob berishga harakat qilishadi.").
"""


def _sumire_response(text, emotion="talking", ticket_created=False, buttons=None, anime_list=None, status=200):
    response_data = {
        "role": "sumire",
        "text": text,
        "emotion": emotion if emotion in ALLOWED_EMOTIONS else "talking",
        "ticket_created": ticket_created,
    }
    
    if buttons:
        response_data["buttons"] = buttons
    if anime_list:
        response_data["anime_list"] = anime_list
        
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


def search_manga_database(query: str, limit: int = 3, offset: int = 0, anime_type: str = "", exclude_keywords=None):
    if exclude_keywords is None:
        exclude_keywords = []

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
        
        anime_type = anime_type.lower()
        if anime_type == "film":
            normalized_results = [
                r for r in normalized_results 
                if r.get("type") and any(k in str(r["type"]).lower() for k in ["film", "kino", "movie"])
            ]
        elif anime_type == "serial":
            normalized_results = [
                r for r in normalized_results 
                if r.get("type") and "serial" in str(r["type"]).lower()
            ]

        if exclude_keywords:
            filtered_results = []
            for r in normalized_results:
                title_lower = r.get('title', '').lower()
                has_excluded_word = any(
                    excl.strip().lower() in title_lower 
                    for excl in exclude_keywords if excl.strip()
                )
                if not has_excluded_word:
                    filtered_results.append(r)
            normalized_results = filtered_results

        return normalized_results[offset : offset + limit]
        
    except Exception as e:
        print(f"Database search error: {e}")
        return []


def _format_search_results(results):
    anime_list = []
    
    for item in results:
        title = item.get('title', 'Nomalum')
        url = item.get('url', '#')
        
        details = []
        if item.get("year"): 
            details.append(str(item["year"]))
            
        if item.get("type"):
            type_str = str(item["type"]).lower()
            if "film" in type_str or "kino" in type_str:
                details.append("Film")
            elif item.get("episodes"): 
                details.append(f"{item['episodes']} qism")
        
        suffix = f" ({', '.join(details)})" if details else ""
        
        anime_list.append({
            "name": f"{title}{suffix}",
            "url": url
        })
        
    return anime_list


def _contains_any(text, words):
    return any(word in text for word in words)


def _is_greeting(text):
    clean_text = re.sub(r'[^a-z]', '', text.lower())
    patterns = [r'^s+a+l+o+m+$', r'^s+l+m+$', r'^q+a+l+e+$', r'^h+i+$']
    return any(re.match(p, clean_text) for p in patterns)


def _notify_admins(application):
    # ТИKЕТЛАРНИ АДМИН БОТ ОРҚАЛИ ГУРУҲГА ЮБОРИШ
    admin_bot_token = os.getenv("ADMIN_BOT_TOKEN")
    admin_chat_id = os.getenv("ADMIN_CHAT_ID")
    
    if not admin_bot_token or not admin_chat_id: 
        return
        
    last_user_msg = application.chat_history[-1].get('text', '') if application.chat_history else ''
    
    message_text = (
        f"🚨 <b>YANGI SHIKOYAT #{application.id}</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"<b>Foydalanuvchi:</b> @{application.username or 'Yashirin'}\n"
        f"<b>Telegram ID:</b> <code>{application.user_id}</code>\n"
        f"<b>Mavzu:</b> {application.subject}\n"
        f"━━━━━━━━━━━━━━\n"
        f"<b>Shikoyat matni:</b>\n<i>{last_user_msg}</i>\n\n"
        f"✍️ <i>Javob berish uchun ushbu xabarga 'Reply' qiling.</i>"
    )
    
    url = f"https://api.telegram.org/bot{admin_bot_token}/sendMessage"
    try:
        requests.post(
            url,
            json={
                "chat_id": admin_chat_id,
                "text": message_text,
                "parse_mode": "HTML"
            },
            timeout=5,
        )
    except Exception as e:
        print(f"Admin group notification error: {e}")


def _create_ticket(user_text, user_id=None, username=None, subject=None):
    try:
        subject = (subject or "Web App muammosi").strip()[:50]
        now = timezone.localtime().strftime("%H:%M")

        uid_int = _safe_int(user_id) if user_id else 0
        if uid_int:
            # Close all previous open tickets for this user to keep a single active ticket channel
            Application.objects.filter(user_id=uid_int, is_closed=False).update(
                is_closed=True,
                is_answered=True
            )

        application = Application.objects.create(
            user_id=uid_int,
            username=username or "",
            category="report",
            subject=subject,
            chat_history=[{"role": "user", "text": user_text, "time": now}],
        )
        Message.objects.create(application=application, text=user_text, is_from_admin=False)
        _notify_admins(application)
        return application
    except Exception as e:
        print(f"Ticket creation error: {e}")
        return None


def _route_without_ai(user_text):
    text_lower = user_text.lower().strip()
    if not text_lower:
        return _sumire_response("Iltimos, matn kiriting. *uzoqqa qaraydi*", "what", status=400)
    if re.search(r'[А-Яа-я]', user_text):
        return _sumire_response("Kechirasiz, men kirill alifbosini tushunmayman. Faqat lotin yozuvida yozing. *yuzini burib oladi*", "face palm")
    if _is_greeting(text_lower):
        return _sumire_response("Salom. Qanday yordam kerak? *sovuq qaraydi*", "talking")
    if _contains_any(text_lower, THANKS_WORDS):
        return _sumire_response("Arzimaydi. Yana ishing tushsa yozarsan. *yengil bosh irg'aydi*", "ty")
    if _contains_any(text_lower, RESOLVED_WORDS):
        return _sumire_response("Yaxshi. Muammo hal bo'lgan bo'lsa, ishimni davom ettiraman. *xotirjam nafas oladi*", "resolve or good")
    return None


def _parse_ai_command(user_text, chat_history_text="", profile=None):
    if not client:
        return {"intent": "chat", "reply": "Ulanishda muammo bor... *kompyuterga uradi*", "emotion": "shocked"}

    profile_context = ""
    if profile and profile.favorite_genres:
        profile_context = f"--- FOYDALANUVCHI PROFILI (XOTIRA) ---\nSevimli janrlari: {profile.favorite_genres}\n\n"

    history_context = f"--- OLDINGI KONTEKST ---\n{chat_history_text}\n\n" if chat_history_text else ""
    full_prompt = f"{profile_context}{history_context}--- YANGI XABAR ---\nUser: {user_text}"

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": INTENT_PROMPT},
                {"role": "user", "content": full_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3, 
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"DeepSeek API Error: {e}")
        return {"intent": "chat", "reply": "Miyam og'rib ketdi... *peshonasini ushlaydi*", "emotion": "face palm"}


def _execute_ai_command(command, user_text, user_id=None, username=None, profile=None):
    intent = command.get("intent", "chat")
    emotion = command.get("emotion", "talking")
    reply = command.get("reply", "Nima deyishni ham bilmayman...").strip()

    save_genre = command.get("save_genre", "").strip()
    if save_genre and profile:
        current_genres = profile.favorite_genres or ""
        if save_genre.lower() not in current_genres.lower():
            if current_genres:
                profile.favorite_genres = f"{current_genres}, {save_genre}"
            else:
                profile.favorite_genres = save_genre
            profile.save()

    if intent == "purchase":
        buttons = [{"text": "🤖 KAWAII BOTGA O'TISH", "url": "https://t.me/Kawaii_uz_bot"}]
        return _sumire_response("Kawaii Pass sotib olish uchun rasmiy @Kawaii_uz_bot botimizga o'ting. *sovuq qaraydi*", "talking", buttons=buttons)

    if intent == "bot_link":
        buttons = [{"text": "KAWAII.UZ GA O'TISH", "url": "https://bot.kawaii.uz/"}]
        return _sumire_response(reply, emotion, buttons=buttons)

    if intent == "search":
        query = command.get("search_query", "").strip()
        exclude_keywords = command.get("exclude_keywords", [])
        
        if not query or query.lower() in ["yo'q", "yoq", "none", "null"]:
            return _sumire_response("Aniq qaysi animeni yoki janrni qidiryapsiz? *kutib turadi*", "what")
            
        anime_type = command.get("anime_type", "")
        limit = min(max(_safe_int(command.get("limit"), 3), 1), 10)
        offset = _safe_int(command.get("offset"), 0)
        
        results = search_manga_database(query, limit=limit, offset=offset, anime_type=anime_type, exclude_keywords=exclude_keywords)
        
        if not results:
            if offset > 0 or exclude_keywords:
                return _sumire_response(f"{reply}\n\n*(Arxivda bu bo'yicha boshqa anime qolmagan ko'rinadi...)*", "canthelp")
            else:
                return _sumire_response(f"Arxivdan '{query}' nomli animeni topolmadim. Balki hali saytga yuklanmagandir. *elkasini qisadi*", "canthelp")
            
        anime_list = _format_search_results(results)
        return _sumire_response(reply, emotion, anime_list=anime_list)

    if intent == "ticket":
        subject = command.get("ticket_subject") or "Web App muammo"
        app = _create_ticket(user_text, user_id=user_id, username=username, subject=subject)
        
        if app:
            # Веб-апп ичида Сумире шунчаки ариза қабул қилинганини совуққина айтади
            return _sumire_response(reply, emotion, ticket_created=True)
        else:
            return _sumire_response("Arizani qabul qilishda texnik xatolik yuz berdi... *xo'rsinadi*", "canthelp")

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

        # Determine client IP and secure TG User ID
        user_ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0] or request.META.get("REMOTE_ADDR", "unknown")
        user_id_int = _safe_int(user_id)

        from django.conf import settings

        # Production security: Require valid Telegram user_id to prevent external spammers/crawlers
        if not settings.DEBUG and user_id_int <= 0:
            return _sumire_response("Faqat Telegram bot ichidan foydalanishga ruxsat berilgan. *sovuq qaraydi*", "fuu", status=403)

        # Cache key for daily request rate-limiting and chat history
        if user_id_int > 0:
            user_daily_key = f"user_limit_tg_{user_id_int}"
            history_key = f"chat_history_tg_{user_id_int}"
        else:
            user_daily_key = f"user_limit_ip_{user_ip}"
            history_key = f"chat_history_ip_{user_ip}"

        user_requests = cache.get(user_daily_key, 0)
        
        # Limit to 30 requests per day per user (IP/Telegram ID)
        if user_requests >= 30:
            return _sumire_response("Bugun judayam ko'p savol berding. Charchadim. Ertaga kel... *ko'zlarini yopadi*", "fuu")

        profile = None
        if user_id_int > 0:
            try:
                profile, _ = Profile.objects.get_or_create(telegram_id=user_id_int)
            except Exception as e:
                print(f"Profile error: {e}")

        chat_history = cache.get(history_key, [])
        history_text = "\n".join([f"{msg['role']}: {msg['text']}" for msg in chat_history])

        command = _parse_ai_command(user_text, history_text, profile)
        
        # Save request increment
        cache.set(user_daily_key, user_requests + 1, timeout=86400)
        
        ai_response = _execute_ai_command(command, user_text, user_id=user_id_int, username=username, profile=profile)

        try:
            reply_data = json.loads(ai_response.content.decode('utf-8'))
            reply_text = reply_data.get("text", "")
            
            chat_history.append({"role": "User", "text": user_text})
            chat_history.append({"role": "Sumire", "text": reply_text})
            cache.set(history_key, chat_history[-6:], timeout=3600)

            # Permanently save chat log to Profile for admin review/analysis
            if profile:
                now_time = timezone.localtime().strftime("%H:%M")
                p_history = list(profile.chat_history) if profile.chat_history else []
                p_history.append({"role": "user", "text": user_text, "time": now_time})
                p_history.append({"role": "admin", "text": reply_text, "time": now_time})
                profile.chat_history = p_history
                profile.save()
        except Exception as e:
            print(f"History cache/db error: {e}")

        return ai_response

    except Exception as exc:
        print(f"API Error: {str(exc)}")
        return _sumire_response("Tizimda xatolik yuz berdi... *boshini ushlaydi*", "canthelp", status=500)