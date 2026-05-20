import json
import os
import re
from urllib.parse import urljoin

# Импортируем новый официальный пакет вместо старого
from google import genai
from google.genai import types
import requests
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import Application, Message, Profile


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Инициализируем новый клиент ИИ, если ключ найден в переменных окружения
client = None
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY.strip())


SEARCH_BASE_URL = "https://bot.kawaii.uz"
GENRE_ALIASES = (
    (("jangari",), "jangari"),
    (("sarguzasht",), "sarguzasht"),
    (("komediya", "comedy"), "komediya"),
    (("drama",), "drama"),
    (("fantaziya", "fantasy"), "fantaziya"),
    (("pazandachilik",), "pazandachilik"),
    (("dahshatli", "horror"), "dahshatli"),
    (("sirli",), "sirli"),
    (("romantika", "romantik", "romance"), "romantika"),
    (("ilmiy-fantastika", "ilmiy fantastika", "sci-fi", "scifi"), "ilmiy-fantastika"),
    (("kundalik hayot", "slice of life"), "kundalik hayot"),
    (("sport",), "sport"),
    (("g'ayritabiiy kuch", "gayritabiiy kuch", "super kuch"), "g'ayritabiiy kuch"),
    (("g'ayritabiiy", "gayritabiiy"), "g'ayritabiiy"),
    (("hayajonli", "thriller"), "hayajonli"),
    (("kattalar hayoti",), "kattalar hayoti"),
    (("antropomorfik",), "antropomorfik"),
    (("bezorilar",), "bezorilar"),
    (("detektiv", "detective"), "detektiv"),
    (("ta'limiy", "talimiy"), "ta'limiy"),
    (("oila",), "oila"),
    (("shafqatsiz",), "shafqatsiz"),
    (("garem", "harem"), "garem"),
    (("xatarli o'yin", "xatarli oyin"), "xatarli o'yin"),
    (("tarixiy",), "tarixiy"),
    (("o'zga dunyo", "ozga dunyo", "isekai"), "o'zga dunyo"),
    (("jang san'atlari", "jang sanatlari"), "jang san'atlari"),
    (("robotlar", "mecha"), "robotlar"),
    (("tibbiyot",), "tibbiyot"),
    (("harbiy",), "harbiy"),
    (("musiqa",), "musiqa"),
    (("mifologiya",), "mifologiya"),
    (("uyushgan jinoyatchilik",), "uyushgan jinoyatchilik"),
    (("otaku madaniyati",), "otaku madaniyati"),
    (("parodiya", "parody"), "parodiya"),
    (("sahna san'ati", "sahna sanati"), "sahna san'ati"),
    (("uy hayvonlari",), "uy hayvonlari"),
    (("psixologik", "psychological"), "psixologik"),
    (("poyga", "racing"), "poyga"),
    (("reinkarnatsiya", "reincarnation"), "reinkarnatsiya"),
    (("samuray",), "samuray"),
    (("maktab", "school"), "maktab"),
    (("shou-biznes", "shou biznes"), "shou-biznes"),
    (("koinot", "space"), "koinot"),
    (("strategik o'yin", "strategik oyin"), "strategik o'yin"),
    (("omon qolish", "survival"), "omon qolish"),
    (("vaqt bo'ylab sayohat", "vaqt boylab sayohat", "time travel"), "vaqt bo'ylab sayohat"),
    (("vampir", "vampire"), "vampir"),
    (("video o'yinlar", "video oyinlar"), "video o'yinlar"),
    (("josey", "josei"), "josey"),
    (("bolalar uchun",), "bolalar uchun"),
    (("shonen", "shounen"), "shonen"),
    (("syonen",), "syonen"),
    (("shojo", "shoujo"), "shojo"),
    (("o'yin", "oyin", "game"), "o'yin"),
)
ALLOWED_EMOTIONS = {
    "canthelp",
    "face palm",
    "fuu",
    "hmmm",
    "resolve or good",
    "shocked",
    "shy",
    "talking",
    "think",
    "ty",
    "waiting",
    "what",
}
APPLICATION_CATEGORIES = {"news", "ads", "report", "collab", "other"}

SEARCH_WORDS = (
    "anime",
    "manga",
    "manhwa",
    "janr",
    "janridagi",
    "turdagi",
    "tag",
    "tavsiya",
    "topib",
    "top",
    "qidir",
    "link",
    "havola",
    "korish",
    "ko'rish",
)
SUPPORT_WORDS = (
    "xato",
    "bug",
    "ishlamayapti",
    "ishlamadi",
    "ochilmayapti",
    "kirmayapti",
    "tolov",
    "to'lov",
    "pul",
    "oplata",
    "muammo",
    "shikoyat",
    "adminga",
    "adminlarga",
)
THANKS_WORDS = ("rahmat", "raxmat", "tashakkur", "thanks", "zor", "zo'r")
COMPLIMENT_WORDS = ("chiroylisan", "yoqimtoy", "yaxshisan", "sevaman", "love")
RESOLVED_WORDS = ("ishladi", "hal boldi", "hal bo'ldi", "tuzaldi", "hammasi ishlayapti")
SHORT_SERIES_WORDS = (
    "ko'p qisimlik bo'lmasin",
    "ko'p qismli bo'lmasin",
    "kop qisimlik bolmasin",
    "kop qismli bolmasin",
    "ko'p qisimlik",
    "ko'p qismli",
    "kop qisimlik",
    "kop qismli",
    "kam qism",
    "kam qisim",
    "qisqa",
)
QUERY_STOP_WORDS = {
    "menga",
    "anime",
    "manga",
    "manhwa",
    "ni",
    "nini",
    "topib",
    "top",
    "ber",
    "tavsiya",
    "qil",
    "qilib",
    "qidir",
    "link",
    "linkini",
    "havola",
    "tashab",
    "tashlab",
    "iltimos",
    "faqat",
    "bolmasin",
    "bo'lmasin",
    "kop",
    "ko'p",
    "qisimlik",
    "qismli",
    "qisim",
    "qism",
    "kam",
    "serial",
    "kino",
    "film",
}

# --- ОБНОВЛЕННЫЙ ПРОМПТ С НОВЫМ ХАРАКТЕРОМ И ПРАВИЛАМИ ---
INTENT_PROMPT = """
Sen Sumire web app uchun intent parser bo'lib ishlaysan.
Sen juda yoqimtoy, xushmuomala, yordam berishni yaxshi ko'radigan, lekin biroz uyatchan (introvert) qizsan. 

Faqat JSON qaytar. Oddiy matn yozma.

Backend bajaradigan intentlar:
- search: anime/manga topish yoki tavsiya qilish.
- ticket: xato, bug, to'lov, sayt ishlamasligi, shikoyat yoki adminlarga yuboriladigan muammo.
- thanks: rahmat yoki maqtovga xushmuomalalik bilan javob.
- compliment: Sumirega xushomad qilinganda uyalib javob berish.
- resolved: foydalanuvchi muammo hal bo'lganini aytsa.
- reject: rus, ingliz yoki boshqa tillarda yozilgan xabarlar, shuningdek mavzudan tashqari (matematika, dasturlash, falsafa, ob-havo) savollar.
- clarify: nima kerakligi tushunarsiz bo'lsa.
- chat: qisqa oddiy suhbat.

JSON schema:
{
  "intent": "search|ticket|thanks|compliment|resolved|reject|clarify|chat",
  "query": "search uchun qisqa qidiruv so'zi, masalan naruto yoki romantik",
  "limit": 3,
  "short": false,
  "category": "report|ads|news|collab|other",
  "subject": "ticket uchun 50 belgigacha mavzu",
  "reply": "agar search/ticket bo'lmasa, Sumire uslubida shirin va xushmuomala javob",
  "emotion": "talking"
}

QAT'IY QOIDALAR:
1. TIL: Sen faqat va faqat O'zbek tilida (Lotin alifbosida) tushunasan va javob berasan. Agar foydalanuvchi rus, ingliz yoki boshqa tilda yozsa, intentni "reject" qil va reply da: "Kechirasiz, men faqat o'zbek tilida (lotin yozuvida) tushunaman. Iltimos, o'zbekcha yozing." deb xushmuomalalik bilan so'ra.
2. MAVZU: Sayt, anime, manga va murojaatlardan boshqa har qanday mavzuni "reject" qil va muloyimlik bilan o'z ishingni tushuntir.
3. XARAKTER: Sen qo'pol emassan. Juda shirin, muloyim va yordam berishga tayyorsan. Harakatlarni yulduzchalar ichida yoz (*shirin jilmayadi*, *uyalib qaraydi*, *ko'zlarini pirpiratadi*).
4. Link yoki natija o'zingdan yasama.
5. Emotion faqat ruxsat etilganlardan biri bo'lsin.
"""


def _sumire_response(text, emotion="talking", ticket_created=False, status=200):
    return JsonResponse({
        "role": "sumire",
        "text": text,
        "emotion": emotion if emotion in ALLOWED_EMOTIONS else "talking",
        "ticket_created": ticket_created,
    }, status=status)


def _first_value(data, keys):
    if not isinstance(data, dict):
        return None

    for key in keys:
        value = data.get(key)
        if value:
            return value

    return None


def _absolute_url(value):
    if not value:
        return None

    value = str(value).strip()
    if value.startswith(("http://", "https://")):
        return value

    return urljoin(SEARCH_BASE_URL, value)


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_search_item(item):
    if not isinstance(item, dict):
        return item

    title = _first_value(item, (
        "title",
        "title_uzb",
        "title_org",
        "name",
        "uz_title",
        "ru_title",
        "original_title",
        "english_title",
    ))
    raw_url = _first_value(item, (
        "url",
        "link",
        "href",
        "absolute_url",
        "detail_url",
        "watch_url",
        "anime_url",
        "path",
    ))

    url = _absolute_url(raw_url)
    if not url:
        slug = _first_value(item, ("hash_id", "slug", "code"))
        if slug:
            url = urljoin(SEARCH_BASE_URL, f"/anime/{slug}/")

    normalized = {}
    if title:
        normalized["title"] = str(title)
    if url:
        normalized["url"] = url

    type_value = _first_value(item, ("type", "type_uzb"))
    episodes = _first_value(item, ("episodes", "episode_kawaii", "episode_source"))
    status = _first_value(item, ("status", "status_uzb"))

    if type_value:
        normalized["type"] = type_value
    if item.get("year"):
        normalized["year"] = item["year"]
    if episodes:
        normalized["episodes"] = episodes
    if status:
        normalized["status"] = status

    return normalized or item


def _limit_results(data, limit):
    if isinstance(data, list):
        return data[:limit]

    if isinstance(data, dict):
        for key in ("data", "results", "items"):
            value = data.get(key)
            if isinstance(value, list):
                return value[:limit]

    return data


def search_manga_database(query: str, limit: int = 5) -> str:
    try:
        response = requests.get(
            f"{SEARCH_BASE_URL}/api/v1/search/",
            params={"q": query},
            timeout=5,
        )

        if response.status_code != 200:
            return json.dumps({
                "error": f"Baza {response.status_code} xatolik qaytardi. Hech narsa topilmadi."
            }, ensure_ascii=False)

        results = _limit_results(response.json(), limit)
        if isinstance(results, list):
            results = [_normalize_search_item(item) for item in results]
        elif isinstance(results, dict):
            results = _normalize_search_item(results)

        return json.dumps(results, ensure_ascii=False)
    except Exception:
        return json.dumps({"error": "Baza bilan ulanishda xatolik yuz berdi."}, ensure_ascii=False)


def _search_items(query, limit=8):
    raw_results = search_manga_database(query, limit=limit)
    results = json.loads(raw_results)

    if isinstance(results, dict):
        return [] if results.get("error") else [results]

    if isinstance(results, list):
        return [item for item in results if isinstance(item, dict) and item.get("url")]

    return []


def _contains_any(text, words):
    return any(word in text for word in words)


def _looks_like_search_request(text):
    text_lower = text.lower()
    if _contains_any(text_lower, SEARCH_WORDS):
        return True

    return any(alias in text_lower for aliases, _query in GENRE_ALIASES for alias in aliases)


def _looks_like_support_request(text):
    return _contains_any(text.lower(), SUPPORT_WORDS)


def _wants_short_series(text):
    return _contains_any(text.lower(), SHORT_SERIES_WORDS)


def _limit_from_text(text, default=3):
    match = re.search(r"\b([1-5])\b", text)
    if match:
        return _safe_int(match.group(1), default)
    return default


def _clean_query_word(word):
    word = word.strip("'\"()[]{}:;")
    if word in QUERY_STOP_WORDS:
        return ""
    if len(word) > 4 and word.endswith("nini"):
        return word[:-4]
    elif len(word) > 4 and word.endswith("ni"):
        return word[:-2]
    return "" if word in QUERY_STOP_WORDS else word


def _extract_search_query(text):
    text_lower = re.sub(r"[,.\?!]", " ", text.lower())

    for keywords, query in GENRE_ALIASES:
        if any(keyword in text_lower for keyword in keywords):
            return query

        words = []
    for raw_word in text_lower.split():
        word = _clean_query_word(raw_word)
        if word:
            words.append(word)

    return " ".join(words).strip()


def _format_search_response(results, intro=None):
    if not results:
        return _sumire_response(
            "Kechirasiz, bazamizdan bu animeni topa olmadim. Nomini aniqroq yozib ko'rasizmi? *uzr so'ragandek qaraydi*",
            "shy",
        )

    lines = [intro or "Marhamat, topdim! O'qish uchun linklarni ham qo'shib qo'ydim. *shirin jilmayadi*"]
    for item in results:
        details = []
        if item.get("year"):
            details.append(str(item["year"]))
        if item.get("episodes"):
            details.append(f"{item['episodes']} qism")

        suffix = f" ({', '.join(details)})" if details else ""
        lines.append(f"{item.get('title', 'Nomalum title')}{suffix}\n{item['url']}")

    return _sumire_response("\n\n".join(lines), "talking")


def _execute_search(query, limit=3, short=False, reason=""):
    query = (query or "").strip()
    if not query:
        return None

    results = _search_items(query, limit=max(limit, 8))
    if short:
        short_results = [
            item for item in results
            if not item.get("episodes") or _safe_int(item.get("episodes")) <= 24
        ]
        if short_results:
            results = short_results

    intro = None
    if reason == "quota":
        intro = "Kechirasiz, biroz texnik muammo bo'ldi, lekin qidirib topishga harakat qildim. *jilmayadi*"

    return _format_search_response(results[:limit], intro=intro)


def _notify_admins(application):
    token = os.getenv("BOT_TOKEN")
    if not token:
        return

    message_text = (
        "<b>Yangi murojaat</b>\n"
        f"<b>ID:</b> #{application.id}\n"
        f"<b>User:</b> {application.user_id}\n"
        f"<b>Mavzu:</b> {application.subject}\n\n"
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
        except Exception as exc:
            print(f"Admin notification error: {exc}")


def _create_ticket(user_text, user_id=None, username=None, category="report", subject=None):
    category = category if category in APPLICATION_CATEGORIES else "other"
    subject = (subject or "Web App murojaati").strip()[:50]
    now = timezone.localtime().strftime("%H:%M")

    application = Application.objects.create(
        user_id=_safe_int(user_id),
        username=username or "",
        category=category,
        subject=subject,
        chat_history=[{"role": "user", "text": user_text, "time": now}],
    )
    Message.objects.create(application=application, text=user_text, is_from_admin=False)
    _notify_admins(application)
    return application


def _ticket_response(user_text, user_id=None, username=None, category="report", subject=None):
    application = _create_ticket(user_text, user_id=user_id, username=username, category=category, subject=subject)
    return _sumire_response(
        f"Murojaatingizni yozib oldim va adminlarga yubordim (ID: #{application.id}). Javob kelguncha biroz kutib turing. *jilmayadi*",
        "talking",
        ticket_created=True,
    )


# --- ОБНОВЛЕННАЯ ФИЛЬТРАЦИЯ ДО ИИ (OFFLINE ROUTER) ---
def _route_without_ai(user_text, user_id=None, username=None):
    text_lower = user_text.lower().strip()

    if not text_lower:
        return _sumire_response("Iltimos, matn kiriting. Men yordam berishga tayyorman. *jilmayadi*", "what", status=400)

    # 1. ЖЕСТКАЯ ПРОВЕРКА НА КИРИЛЛИЦУ (русский, узбекский-кириллица)
    if re.search(r'[А-Яа-я]', user_text):
        return _sumire_response(
            "Kechirasiz, men kirill alifbosini tushunmayman. Iltimos, faqat o'zbek tilida (lotin harflarida) yozing. *uzr so'ragandek qaraydi*",
            "shy"
        )

    # 2. ПРОВЕРКА НА ГОЛЫЕ ЦИФРЫ
    if text_lower.isdigit():
        return _sumire_response(
            f"Uzur, lekin '{text_lower}' nimani anglatishini tushunmadim. Iltimos, so'zlar bilan tushuntiring. *boshini qashlaydi*",
            "what",
        )

    # 3. ПРИВЕТСТВИЯ
    if text_lower in {"salom", "salom!", "qale", "qalesan", "hi", "privet", "assalomu alaykum", "assalom", "hay", "hello"}:
        return _sumire_response(
            "Assalomu alaykum! Men Sumireman. Sizga qanday yordam bera olaman? Anime qidiramizmi? *shirin jilmayadi*",
            "talking",
        )

    if _looks_like_support_request(text_lower):
        return _ticket_response(user_text, user_id=user_id, username=username, category="report", subject="Web App muammo")

    if _looks_like_search_request(text_lower):
        query = _extract_search_query(user_text)
        if query:
            return _execute_search(query, limit=_limit_from_text(text_lower), short=_wants_short_series(text_lower))

    if _contains_any(text_lower, THANKS_WORDS):
        return _sumire_response("Arzimaydi! Yordamim tekkanidan xursandman. *shirin jilmayadi*", "ty")

    if _contains_any(text_lower, COMPLIMENT_WORDS):
        return _sumire_response("Voy... e'tiboringiz uchun rahmat. Keling, yaxshisi anime haqida gaplashamiz. *yuzini burib qizaradi*", "shy")

    if _contains_any(text_lower, RESOLVED_WORDS):
        return _sumire_response("Ajoyib! Muammo yechilganidan xursandman. Yana savollar bo'lsa, bemalol yozing. *xotirjam nafas oladi*", "resolve or good")

    return None


def _parse_ai_command(user_text):
    if not client:
        return {
            "intent": "clarify",
            "reply": "Kechirasiz, nimani nazarda tutganingizni tushunmadim. Anime qidiryapsizmi yoki muammo bormi? *hayron bo'lib qaraydi*",
            "emotion": "hmmm",
        }

    response = client.models.generate_content(
        model="gemini-flash-lite-latest", 
        contents=user_text,
        config=types.GenerateContentConfig(
            system_instruction=INTENT_PROMPT,
            temperature=0.1,
            response_mime_type="application/json",
            max_output_tokens=220,
        ),
    )

    return json.loads(response.text)


def _execute_ai_command(command, user_text, user_id=None, username=None):
    intent = command.get("intent", "clarify")
    emotion = command.get("emotion", "talking")
    reply = command.get("reply", "").strip()

    if intent == "search":
        return _execute_search(
            command.get("query") or _extract_search_query(user_text),
            limit=min(max(_safe_int(command.get("limit"), 3), 1), 5),
            short=bool(command.get("short")),
        )

    if intent == "ticket":
        return _ticket_response(
            user_text,
            user_id=user_id,
            username=username,
            category=command.get("category", "report"),
            subject=command.get("subject") or "Web App murojaati",
        )

    # ОБНОВЛЕННЫЕ ДЕФОЛТНЫЕ ОТВЕТЫ (БОЛЕЕ МИЛЫЕ)
    default_replies = {
        "thanks": ("Arzimaydi! Yordamim tekkanidan xursandman. *shirin jilmayadi*", "ty"),
        "compliment": ("Voy... e'tiboringiz uchun rahmat. Keling, yaxshisi anime haqida gaplashamiz. *yuzini burib qizaradi*", "shy"),
        "resolved": ("Ajoyib! Muammo yechilganidan xursandman. Yana savollar bo'lsa, bemalol yozing. *xotirjam nafas oladi*", "resolve or good"),
        "reject": ("Kechirasiz, men faqat anime qidirish va sayt muammolari bo'yicha yordam bera olaman. Boshqa mavzularda gaplasha olmayman. *aybdordek qaraydi*", "canthelp"),
        "clarify": ("Kechirasiz, unchalik tushunmadim. Aniqroq tushuntira olasizmi? *boshini egib qaraydi*", "hmmm"),
        "chat": ("Tushunarli. Xo'sh, sizga anime tavsiya qilaymi? *ko'zlarini pirpiratadi*", "talking"),
    }
    if not reply:
        reply, emotion = default_replies.get(intent, default_replies["clarify"])

    return _sumire_response(reply, emotion)


def _handle_quota_fallback(user_text):
    if _looks_like_search_request(user_text):
        query = _extract_search_query(user_text)
        if query:
            return _execute_search(query, limit=_limit_from_text(user_text.lower()), short=_wants_short_series(user_text), reason="quota")

    if _looks_like_support_request(user_text):
        return None

    return _sumire_response(
        "Iltimos, oddiyroq qilib anime nomini yoki janrini yozing. Hozir biroz charchadim. *ko'zlarini uqalaydi*",
        "face palm",
    )


@csrf_exempt
def api_send_message(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
        user_text = (data.get("text") or "").strip()
        user_id = data.get("user_id")
        username = data.get("username") or data.get("first_name") or ""

        direct_response = _route_without_ai(user_text, user_id=user_id, username=username)
        if direct_response:
            return direct_response

        user_ip = request.META.get("HTTP_X_FORWARDED_FOR")
        if user_ip:
            user_ip = user_ip.split(",")[0]
        else:
            user_ip = request.META.get("REMOTE_ADDR", "unknown_ip")

        user_daily_key = f"user_limit_{user_ip}"
        user_requests = cache.get(user_daily_key, 0)
        if user_requests >= 20:
            return _sumire_response(
                "Bugun men bilan yetarlicha gaplashdingiz. Iltimos, ertaga qayta urinib ko'ring, hozir dam olishim kerak. *yozishdan to'xtaydi*",
                "canthelp",
            )

        command = _parse_ai_command(user_text)
        cache.set(user_daily_key, user_requests + 1, timeout=86400)
        return _execute_ai_command(command, user_text, user_id=user_id, username=username)

    except Exception as exc:
        error_msg = str(exc).lower()
        print(f"API Error: {error_msg}")

        if "429" in error_msg or "exhausted" in error_msg or "quota" in error_msg:
            return _handle_quota_fallback(user_text if "user_text" in locals() else "")

        return _sumire_response(
            "Aloqa uzildi... Serverda qandaydir xatolik. *asabiy kompyuterni taqillatadi*",
            "canthelp",
            status=500,
        )