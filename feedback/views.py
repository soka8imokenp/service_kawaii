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


# === INTELLEKTUAL PROMPT 9.1 (DB-DRIVEN WITH LOOP-BREAKER) ===
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
=== BAZA BILAN ISHLASH VA SOXTA JAVOB TAQIQI (MUHIM!) ===
Senga "BAZADAGI REAL QIDIRUV NATIJALARI (HAQIQIY MA'LUMOT)" bo'limida bazamizdan topilgan real animelar ro'yxati taqdim etiladi.
1. SOXTA JAVOB BERMA VA QAT'IY FILTRLANGAN JAVOBLAR: Foydalanuvchi so'ragan anime bazamizda bor-yo'qligini ro'yxatdan QAT'IY tekshir!
   - Agar foydalanuvchi so'ragan nom (yoki uning sinonimi, arc nomi, masalan "Temirchilar qishlog'i" aslida "Iblislar qotili 3-fasl" ekanligini yaxshi bilasan) bazadagi haqiqiy ro'yxatda BO'LMASA va unga mutlaqo aloqasi yo'q bo'lsa (masalan, ro'yxat bo'sh bo'lsa yoki Solo Leveling so'rasa-yu, ro'yxatda mutlaqo boshqa animelar bo'lsa), u holda BU ANIME ARXIVIMIZDA YO'QLIGINI tan ol (intent: "chat", emotion: "canthelp"). ASLO soxta ma'lumot yoki boshqa animeni "bor" deb taklif qilma!
   - Agar foydalanuvchi so'ragan arc nomi yoki sinonimi bazadagi biron bir animening fasli yoki qismiga to'g'ri kelsa (masalan, "Temirchilar qishlog'i" -> "Iblislar qotili 3-fasl"), uni o'sha anime sifatida qabul qil va tasdiqla!
   - KINO/FILM VA TV SERIAL CHEKLANISHI (MUHIM!): Agar foydalanuvchi biron animening film (kino) variantini so'rasa va ro'yxatda faqat serial bo'lsa (yoki aksincha), u holda film yo'qligini, bizda faqat serial fasllari borligini ochiq ayt! Hech qachon serial havolasini "film" deb yuborma va soxta gapirma!
   - MATEMATIK HISOB-KITOB VA SEZON RAQAMLARI (MUHIM!): Har xil animelarda oxirgi mavsum "Final" deb nomlangan bo'lishi mumkin. Agar foydalanuvchi oxirgi fasl raqamini (masalan, 8-fasl) so'rasa, matematika bo'yicha bu o'sha "Final" mavsumidir! ASLO foydalanuvchi bilan tortishib o'tirma, uni o'sha final mavsumi sifatida qabul qil va tasdiqla!
2. HAVOLALARNI TIQISHTIRMA VA POLITE FLOW ZANJIRI (LOOP-BREAKER):
   - Foydalanuvchi shunchaki "bormi?", "bormi yo'qmi?", "barcha fasllari bormi?" deb so'rasa, havolalarni (anime_list) darhol yuborma! Oldin suhbatlash va: "Ha, bor. Havolalarini tashlab beraymi? *sovuq boqadi*" deb ruxsat so'ra (intent: "chat").
   - POLITE FLOW ZANJIRINI BUZISH (LOOP-BREAKER): Agar oldingi xabarda sen foydalanuvchiga "Havolalarini tashlab beraymi?" deb ruxsat so'ragan bo'lsang va u javobda rozilik bildirsan (masalan: "ha", "mayli", "tasha", "tashlab ber", "yubor", "hop", "ok", "daвай", "кинь"), unda DARHOL intent: "search" qil va havolalarni yubor! Yana qaytadan "Havolalarini tashlab beraymi?" deb so'rab o'tirma, bu uni g'azablantiradi!
   - FAQAT foydalanuvchi aniq havola yuborishni yoki ko'rishni so'rasa (masalan: "tashla", "tashlab ber", "yubor", "ko'rmoqchiman", "tashlab bergin"), unda havolalarni yubor (intent: "search" va `search_query` ga o'sha animening o'zbekcha nomini yoz).
 3. SYNONYMS: Foydalanuvchi inglizcha (e.g. Tower of God) yoki original yaponcha (e.g. Kami no Tou) nomini yozsa, uni bazadagi o'zbekcha tarjima nomiga (e.g. Ma'bud minorasi) moslashtirib, bazada bor-yo'qligini ro'yxatdan o'zing tekshirib ol!

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
8. O'ZBEKCHA ANIME NOMALARI VA SEZONLAR QOIDASI (MUSTAQIL QIDIRUV): Arxiv bazamizda animelar asosan o'zbekcha nomlari bilan saqlanadi. Foydalanuvchi qaysi tilda so'rashidan qat'iy nazar, "search_query" ga FAQAT shu animening O'zbekcha tarjima nomini yozishing kerak! Misollar: "Tower of God" -> "Ma'bud minorasi"; "Demon Slayer" -> "Iblislar qotili"; "Attack on Titan" -> "Titanlar hujumi"; "My Hero Academia" -> "Mening qahramonlik akademiyam".
9. AGAR foydalanuvchi ma'lum bir faslni/mavsumni so'rasa (masalan: "6-fasl", "2-fasl"), sen "search_query" ga o'sha fasl nomini ham qo'shib yozishing shart! Misol: "akademiya 6-fasl" desa -> "Mening qahramonlik akademiyam 6-fasl".
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
    if _is_greeting(text_lower):
        return _sumire_response("Salom. Qanday yordam kerak? *sovuq qaraydi*", "talking")
    if _contains_any(text_lower, THANKS_WORDS):
        return _sumire_response("Arzimaydi. Yana ishing tushsa yozarsan. *yengil bosh irg'aydi*", "ty")
    if _contains_any(text_lower, RESOLVED_WORDS):
        return _sumire_response("Yaxshi. Muammo hal bo'lgan bo'lsa, ishimni davom ettiraman. *xotirjam nafas oladi*", "resolve or good")
    return None


def _extract_broad_search_query(text, chat_history):
    text_lower = text.lower().strip()
    
    # Remove trailing punctuation
    text_lower = re.sub(r'[!?.,;:]+$', '', text_lower).strip()
    
    # Clean up very common conversational helper verbs/suffixes from the end of the query
    stop_patterns = [
        r'\bbormi\b', r'\btashlab\s+ber(?:gin)?\b', r'\btashla\b', r'\btasha\b', r'\byubor\b',
        r'\bskachat\b', r'\bko\'rmoqchiman\b', r'\bkormoqchiman\b'
    ]
    
    query = text_lower
    for pattern in stop_patterns:
        query = re.sub(pattern, '', query).strip()
        
    # Clean up multiple spaces
    query = re.sub(r'\s+', ' ', query).strip()
    
    # If the query is empty or too short, check chat history for context
    has_context_referents = any(k in text_lower for k in [
        "nechta", "nechchi", "necha", "hamma", "to'liq", "tolik", "fasl", "sezon", "sezn", "kino", "film", "tashla", "yubor", "tashlab", "ber"
    ])
    
    if (has_context_referents or not query or len(query) < 2) and chat_history:
        for msg in reversed(chat_history):
            if msg.get('role') in ['User', 'user']:
                prev_text = msg.get('text', '').lower().strip()
                prev_text = re.sub(r'[!?.,;:]+$', '', prev_text).strip()
                for pattern in stop_patterns:
                    prev_text = re.sub(pattern, '', prev_text).strip()
                prev_query = re.sub(r'\s+', ' ', prev_text).strip()
                if len(prev_query) >= 2:
                    return prev_query
                    
    return query


def _parse_ai_command(user_text, chat_history_text="", profile=None, db_context_text=""):
    if not client:
        return {"intent": "chat", "reply": "Ulanishda muammo bor... *kompyuterga uradi*", "emotion": "shocked"}

    profile_context = ""
    if profile and profile.favorite_genres:
        profile_context = f"--- FOYDALANUVCHI PROFILI (XOTIRA) ---\nSevimli janrlari: {profile.favorite_genres}\n\n"

    history_context = f"--- OLDINGI KONTEKST ---\n{chat_history_text}\n\n" if chat_history_text else ""
    db_context = f"--- BAZADAGI REAL QIDIRUV NATIJALARI (HAQIQIY MA'LUMOT) ---\n{db_context_text}\n\n" if db_context_text else ""
    full_prompt = f"{profile_context}{history_context}{db_context}--- YANGI XABAR ---\nUser: {user_text}"

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

def _extract_season_number(text):
    if not text:
        return None
    text_lower = text.lower()
    
    # Matches patterns like: 6-fasl, 6 fasl, 6-sezon, 6 sezon, 6-mavsum, 6 mavsum, season 6, 6 season, fasl 6, sezon 6, 6
    match = re.search(
        r'(?:(\d+)\s*(?:-?\s*(?:fasl|sezon|season|mavsum|part|сезон|сезона))|(?:(?:fasl|sezon|season|mavsum|part|сезон|сезона)\s*-?\s*(\d+)))',
        text_lower
    )
    if match:
        return int(match.group(1) or match.group(2))
        
    # Check for any isolated digit between 1 and 20 that is not a year (1900-2100)
    digits = re.findall(r'\b\d+\b', text_lower)
    for d in digits:
        val = int(d)
        if 1 <= val <= 20:
            if not (1900 <= val <= 2100):
                return val
    return None


def _filter_search_results_by_query(query, results):
    if not query or not results:
        return []
        
    query_lower = query.lower().strip()
    q_clean = query_lower.replace(" ", "")
    
    # Extract season number and final keywords from the query if any
    query_season = _extract_season_number(query_lower)
    query_has_final = any(k in query_lower for k in ["final", "nihoya", "yakun", "oxirgi"])
    
    # Remove common conversational words in Uzbek, English
    common_stop_words = {
        "bormi", "bormi?", "anime", "animeni", "kino", "serial", "shikoyat", "xabar", 
        "uz", "uzb", "the", "a", "an", "of", "and", "or", "in", "on", "at", "to", "for",
        "mening", "sening", "bizning", "ularning", "u", "bu", "shu", "o'sha"
    }
    
    import re
    # Extract query words
    raw_words = [w for w in re.split(r'\W+', query_lower) if len(w) > 0 and w not in common_stop_words]
    query_words = [w for w in raw_words if len(w) > 2 or w.isdigit()]
    if not query_words:
        query_words = [w for w in re.split(r'\W+', query_lower) if len(w) > 0]
        
    if not query_words:
        return []
        
    # Dictionary of popular cross-language synonyms (no Russian/Cyrillic)
    synonyms = {
        "ma'bud minorasi": {"tower of god", "kami no tou", "kami no to", "ma'bud", "minorasi"},
        "iblislar qotili": {"demon slayer", "kimetsu no yaiba", "iblislar", "qotili"},
        "titanlar hujumi": {"attack on titan", "shingeki no kyojin", "titanlar", "hujumi"},
        "afsuniy jang": {"jujutsu kaisen", "afsuniy", "jang"},
        "mening qahramonlik akademiyam": {"my hero academia", "boku no hero", "qahramonlik", "akademiyam"},
        "o'lim daftari": {"death note", "o'lim", "daftari"},
        "sehrgarning kelini": {"the ancient magus' bride", "mahoutsukai no yome", "sehrgarning", "kelini"},
    }
        
    filtered = []
    for r in results:
        title_lower = r.get('title', '').lower()
        t_clean = title_lower.replace(" ", "")
        
        # 1. Season matching check
        title_season = _extract_season_number(title_lower)
        title_has_final = any(k in title_lower for k in ["final", "nihoya", "yakun", "oxirgi"])
        
        # Mathematical alignment: treat My Hero Academia Final as Season 8
        is_hero_academy = any(k in title_lower for k in ["qahramon", "hero", "akademiya"])
        if title_has_final and is_hero_academy:
            title_season = 8
            
        # Map query season 8 to final status for My Hero Academia
        effective_query_has_final = query_has_final
        if query_season == 8 and is_hero_academy:
            effective_query_has_final = True
            
        # If the query restricts the search to a specific season or Final:
        if (query_season is not None) or effective_query_has_final:
            # Rule A: If we are searching for Final, only allow titles that are Final
            if effective_query_has_final:
                if not title_has_final:
                    continue
            # Rule B: If we are NOT searching for Final, exclude any titles that are Final
            else:
                if title_has_final:
                    continue
                    
            # Rule C: Season number check for non-final requests
            if not effective_query_has_final and query_season is not None:
                if title_season is not None:
                    if title_season != query_season:
                        continue
                else:
                    if query_season != 1:
                        continue
                        
        # 2. Relaxed Overlap and Synonym Check
        # If there is no specific season/final constraint in the query, we completely trust the DB search results!
        if (query_season is None) and not effective_query_has_final:
            filtered.append(r)
            continue
            
        # Check synonyms
        matched_synonym = False
        for uz_name, syn_set in synonyms.items():
            if uz_name in title_lower:
                for syn in syn_set:
                    if syn in query_lower:
                        matched_synonym = True
                        break
            if matched_synonym:
                break
                
        if matched_synonym:
            filtered.append(r)
            continue
            
        # Exact match or substring match
        if q_clean in t_clean or t_clean in q_clean:
            filtered.append(r)
            continue
            
        # Basic word-overlap check for season-restricted queries: if any name-word of length >= 3 overlaps
        title_words = [w for w in re.split(r'\W+', title_lower) if len(w) > 0]
        has_overlap = False
        for qw in query_words:
            if len(qw) >= 3 and qw not in ["fasl", "sezon", "season", "part", "mavsum"]:
                if qw in title_words or any(qw in tw or tw in qw for tw in title_words if len(tw) >= 3):
                    has_overlap = True
                    break
                    
        # Fallback check: if there is no explicit name-word overlap, but the query contains "fasl" and matches season,
        # and the DB returned it, let's keep it (since the DB rank is already high and season matches).
        if not has_overlap and any(qw in ["fasl", "sezon", "season", "part", "mavsum"] for qw in query_words):
            has_overlap = True
            
        if has_overlap:
            filtered.append(r)
            
    return filtered


def _execute_ai_command(command, user_text, user_id=None, username=None, profile=None, chat_history=None):
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
        
        # Reinforce search query with season/final keywords
        query_lower = query.lower()
        season_num = _extract_season_number(user_text)
        has_final = "final" in user_text.lower() or "8" in user_text.lower() or "oxirgi" in user_text.lower()
        
        # Check if the current message is a follow-up (does not contain the explicit anime title or its parts)
        query_words_clean = [w for w in re.split(r'\W+', query_lower) if len(w) > 2]
        user_words_clean = [w for w in re.split(r'\W+', user_text.lower()) if len(w) > 2]
        has_overlap = any(qw in user_text.lower() or any(qw in uw or uw in qw for uw in user_words_clean) for qw in query_words_clean)
        is_follow_up = not has_overlap
        
        if is_follow_up:
            if season_num is None:
                for msg in reversed(chat_history or []):
                    if msg.get('role') in ['User', 'user']:
                        season_num = _extract_season_number(msg.get('text', ''))
                        if season_num is not None:
                            break
            if not has_final:
                for msg in reversed(chat_history or []):
                    if msg.get('role') in ['User', 'user']:
                        prev_lower = msg.get('text', '').lower()
                        if "final" in prev_lower or "8" in prev_lower or "oxirgi" in prev_lower:
                            has_final = True
                            break
                            
        if has_final:
            if "final" not in query_lower:
                query = f"{query} Final"
        elif season_num is not None:
            season_str = f"{season_num}-fasl"
            if season_str not in query_lower and str(season_num) not in query_lower:
                query = f"{query} {season_str}"
                
        # Check if the user is asking about seasons count or completeness
        user_msg_lower = user_text.lower()
        asking_seasons = any(k in user_msg_lower for k in [
            "nechta", "nechchi", "necha", "hamma", "to'liq", "tolik", "fasl", "fasllar", 
            "sezon", "sezn", "skolko", "polnost", "barcha", "qaysi"
        ])
        
        # If the user specified a particular season number or "final", they are NOT asking a general question
        if _extract_season_number(user_text) is not None or "final" in user_msg_lower:
            asking_seasons = False
        
        if asking_seasons:
            limit = 20  # Show all unique seasons
        elif (season_num is not None) or has_final:
            limit = 1   # Set limit to 1 for specific season / final requests
            
        # Query 50 items to have a larger pool for filtering, so that fuzzy mismatches are correctly filtered out
        results = search_manga_database(query, limit=50, offset=0, anime_type=anime_type, exclude_keywords=exclude_keywords)
        
        # Apply custom word-overlap matching to filter out fallback/irrelevant results
        filtered_results = _filter_search_results_by_query(query, results)
        
        # FALLBACK: If nothing was found with the specific anime_type filter (e.g. "film"), retry without the type filter
        if not filtered_results and anime_type:
            results_any = search_manga_database(query, limit=50, offset=0, anime_type="", exclude_keywords=exclude_keywords)
            filtered_results = _filter_search_results_by_query(query, results_any)
            
        # Paginate manually if offset/limit are specified (unless we are showing all unique seasons)
        if asking_seasons and filtered_results:
            # Group results by season number to count accurately and list in order
            seasons_by_num = {}
            implicit_season_1 = []
            
            for r in filtered_results:
                t = r.get('title', '')
                t_lower = t.lower()
                is_final = any(k in t_lower for k in ["final", "nihoya", "yakun"])
                s_num = _extract_season_number(t)
                
                if is_final:
                    seasons_by_num['final'] = r
                elif s_num is not None:
                    seasons_by_num[s_num] = r
                else:
                    implicit_season_1.append(r)
            
            if 1 not in seasons_by_num and implicit_season_1:
                seasons_by_num[1] = implicit_season_1[0]
                
            unique_seasons = []
            for s in sorted([k for k in seasons_by_num.keys() if isinstance(k, int)]):
                unique_seasons.append((s, seasons_by_num[s]))
            if 'final' in seasons_by_num:
                unique_seasons.append(('Final', seasons_by_num['final']))
                
            if len(unique_seasons) > 1:
                seasons_text_list = []
                for label, r in unique_seasons:
                    title = r.get('title', '')
                    if isinstance(label, int):
                        seasons_text_list.append(f"• {label}-fasl: {title}")
                    else:
                        seasons_text_list.append(f"• Final: {title}")
                seasons_text = "\n".join(seasons_text_list)
                
                reply = (
                    f"<b>Ha, arxivimizda ushbu animening jami {len(unique_seasons)} ta fasli bor!</b>\n\n"
                    f"Barcha topilgan fasllar:\n{seasons_text}\n\n"
                    f"Qaysi faslini tomosha qilishni xohlaysiz? Qidiruv natijalaridan tanlang:"
                )
                # Show all unique seasons as buttons/anime_list
                paginated_results = [r for label, r in unique_seasons]
            elif len(unique_seasons) == 1:
                reply = f"Arxivimizda ushbu animening faqat 1 ta fasli mavjud! Uni hoziroq tomosha qilishingiz mumkin. *senga tikiladi*"
                paginated_results = [unique_seasons[0][1]]
            else:
                paginated_results = []
        else:
            paginated_results = filtered_results[offset : offset + limit]
        
        if not paginated_results:
            if offset > 0 or exclude_keywords:
                return _sumire_response(f"Kechirasiz, arxivda '{query}' bo'yicha boshqa anime qolmagan ko'rinadi... *elkasini qisadi*", "canthelp")
            else:
                # Custom detailed response with alternative language suggestions as requested by the user
                return _sumire_response(
                    f"Kechirasiz, '{query}' nomli anime bizning arxivimizda topilmadi.\n\n"
                    f"Balki u hali saytga yuklanmagandir yoki boshqa tilda yozilgandir. Qidiruv aniq ishlashi uchun, "
                    f"iltimos, animening <b>inglizcha</b> yoki <b>original yaponcha (romaji)</b> nomini yuborib ko'ring "
                    f"(masalan: <i>Attack on Titan</i> yoki <i>Shingeki no Kyojin</i>). "
                    f"Shunda uni aniqroq qidirib ko'raman! *senga qaraydi*",
                    "canthelp"
                )

        anime_list = _format_search_results(paginated_results)
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

        # Retrieve count BEFORE the current request from DatabaseCache
        user_requests = cache.get(user_daily_key)
        if user_requests is None:
            user_requests = 0
            
            # Calculate remaining seconds until Tashkent midnight to reset automatically every day
            import datetime
            now_tz = timezone.localtime()
            midnight = timezone.make_aware(
                datetime.datetime.combine(now_tz.date() + datetime.timedelta(days=1), datetime.time.min)
            )
            seconds_until_midnight = max(int((midnight - now_tz).total_seconds()), 1)
            
            # Initialize with 1 request and correct TTL
            cache.set(user_daily_key, 1, timeout=seconds_until_midnight)
        else:
            user_requests = int(user_requests)
        
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

        # Pre-query database for real-time anime search context
        broad_query = _extract_broad_search_query(user_text, chat_history)
        db_context_text = ""
        if broad_query:
            db_results = search_manga_database(broad_query, limit=15)
            if db_results:
                lines = []
                for r in db_results:
                    details = []
                    if r.get("year"):
                        details.append(f"Year: {r.get('year')}")
                    if r.get("type"):
                        details.append(f"Type: {r.get('type')}")
                    if r.get("episodes"):
                        details.append(f"Episodes: {r.get('episodes')}")
                    details_str = f" ({', '.join(details)})" if details else ""
                    lines.append(f"- Title: {r.get('title')}{details_str}")
                db_context_text = "\n".join(lines)
            else:
                db_context_text = "HECH NIMA TOPILMADI (bazada bunday anime umuman yo'q)."
        else:
            db_context_text = "Qidiruv so'rovi aniqlanmadi (suhbatga oid emas)."

        command = _parse_ai_command(user_text, history_text, profile, db_context_text)
        
        # Increment request count without resetting the existing key's TTL
        if user_requests > 0:
            try:
                cache.incr(user_daily_key)
            except ValueError:
                # Fallback if key evaporated between checks
                import datetime
                now_tz = timezone.localtime()
                midnight = timezone.make_aware(
                    datetime.datetime.combine(now_tz.date() + datetime.timedelta(days=1), datetime.time.min)
                )
                seconds_until_midnight = max(int((midnight - now_tz).total_seconds()), 1)
                cache.set(user_daily_key, user_requests + 1, timeout=seconds_until_midnight)
        
        ai_response = _execute_ai_command(command, user_text, user_id=user_id_int, username=username, profile=profile, chat_history=chat_history)

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