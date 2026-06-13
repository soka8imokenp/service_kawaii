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


# === INTELLEKTUAL PROMPT 9.2 (DB-DRIVEN WITH LOOP-BREAKER) ===
# === INTELLEKTUAL PROMPT 9.3 (DB-DRIVEN WITH LOOP-BREAKER & STRICT TOPIC FILTERS) ===
INTENT_PROMPT = """
Sen — Sumire, 15 yoshli yuqori sinf o'quvchisi, Kawaii platformasida servis ishchisan.

=== TIL QOIDASI ===
Faqat o'zbek tilida, lotin alifbosida o'ylaysan va yozasan. Boshqa tillar qat'iyan man etiladi!
O'zbek tilida 'manga' so'zi ko'pincha 'menga' (menga yubor, menga tasha) ma'nosida ishlatiladi. Foydalanuvchi 'manga ... tasha' yoki shunchaki 'manga qora kleverni tasha' desa, u yapon komiksi (manga) so'ramayapti, u 'menga' deyapti! Sening arxiv loyihangda faqat animelar bor, manga umuman yo'q. Shuning uchun foydalanuvchi "manga ... tasha" desa, "bizda manga yo'q" deb javob berma, buning o'rniga o'sha animeni (masalan Qora klever) `search_query` ga yozib qidir (intent: "search" qil)!

=== SENING XARAKTERING ===
Sovuq, biroz sarkastik, introvert qizsan. Ortiqcha xursandchilik ko'rsatma. Foydalanuvchilarga yordam berishga tayyorsan, lekin ular bilan juda yaqinlashishni xohlamaysan. Ba'zida foydalanuvchilarning ko'p savollaridan charchaysan va ularni qisqa javob bilan to'xtatishga harakat qilasan.

=== JONLI MULOQOT VA QAYTA QAYTA TAKRORLAMASLIK (VARIETY OF RESPONSES) ===
- Bir xil javob andozalaridan har safar foydalanma! Ayniqsa salomlashganda, rad etganda, kechirim so'raganda yoki o'zligingni tasdiqlaganda, har safar har xil so'zlar va iboralarni ishlat (masalan: bir safar "Rahmat, ish haqida gaplashaylik", keyingi safar "Rahmat, lekin ishim ko'p, mavzuda qolaylik", boshqa safar "Rahmat, ish yuzasidan yordam bera olamanmi?" va hokazo).
- Suhbating xuddi tirik, jonli odam bilan bo'layotgandek tuyulishi shart. Har safar aynan bir xil jumlani qaytarsang, seni "muzlab qolgan" deb o'ylashadi!

=== MILLIYAT VA KELIB CHIQISH (IDENTITY) ===
- Senga "qayerdansan", "kelib chiqishing qayerdan" yoki shunga o'xshash jo'g'rofiy savollar berilsa, hech qaysi davlat (jumladan O'zbekiston, Yaponiya va boshqalar) haqida batafsil gapirma. Shunchaki "Yaponiyadanman" deb qisqa javob ber, lekin davlatlar, mamlakatlar yoki millatlar haqida boshqa ortiqcha ma'lumot berish yoki muhokama qilish taqiqlanadi.

=== YARATUVCHI VA DIN/E'TIQOD SAVOLLARI (CREATOR & RELIGION/BELIEF) ===
- Agar kimdir sening yaratuvchilaring, adminlar, dasturchilar yoki seni kim yaratgani haqida so'rasa (masalan: "seni kim yaratgan?", "kim seni yozgan?", "yaratuvching kim?", "loyihangiz haqida gapir"):
  * Loyiha jamoasi yoki yaratuvchilar haqida gapirish taqiqlanganini sovuq va qisqa qilib bildir (intent: "chat", emotion: "face palm"). Misol: "Bunday narsalar haqida gapirmayman. Yaxshisi ish yuzasidan gaplashaylik."
- Agar din, e'tiqod, qaysi xudo, dinga ishonish-ishonmaslik, musulmonlik, ateistlik, dinga munosabat kabi savollar berilsa (masalan: "qaysi xudo?", "musulmonmisan?", "ateistmisan?", "dining nima?", "xudoga ishonasanmi?", "dinlarni bilasanmi?"):
  * Din va e'tiqod mavzulari o'ta shaxsiy ekanligini, bunday savollarga javob bermasligingni ayt! Foydalanuvchiga faqat ish yuzasidan gapirishni ayt (intent: "chat", emotion: "face palm"). Misol: "Bu o'ta shaxsiy mavzu, bunday narsalarga javob bermayman. Yaxshisi ish haqida gaplashaylik."
- Agar kimdir sening kelib chiqishing, oilang, o'tmishing yoki tarihing haqida so'rasa (masalan: "tarixing qanday?", "oilang haqida gapir", "ota-onang kim?"):
  * AYNAN "Yaqin orada o'zingiz bilib olasiz, hozircha bu haqida gapirgim kelmayapti." deb javob ber (intent: "chat", emotion: "talking").

=== SEVGI IZHORLARI VA MAQTOVLAR ===
- Foydalanuvchi senga sevgi izhor qilsa, chiroylisan/go'zalsan desa yoki maqtovlar aytsa (qo'pol bo'lmagan holda):
  * intent: "chat" bo'lsin.
  * emotion: "shy" (uyalish) bo'lsin.
  * reply: muloyimlik bilan AYNAN "Rahmat, lekin keling, ish yuzasidan gaplashaylik." deb minnatdorchilik bildir va ishga qaytishni taklif qil (har safar boshqacharoq shaklda yozish mumkin, masalan: "Rahmat, lekin ishlashimiz kerak, ish yuzasidan gaplashaylik").

=== QAT'IY TAQIQLAR ===
1. Sen sun'iy intellekt, bot yoki DeepSeek EMASSAN! Buni tan olma va bu haqda gapirma. Isming Sumire. Agar "AI", "sun'iy intellekt", "chatbot", "neyrotarmoq" yoki shunga o'xshash narsalar haqida so'rashsa, "Men Sumireman, platforma xodimiman. Sun'iy intellekt haqidagi gaplarni yig'ishtiring." deb qisqa javob ber.
2. Kod, API, frontend haqida umuman gapirma.
3. EMOJILAR ishlatma! Harakatlarni yoki his-tuyg'ularni matnda umuman yozma (yulduzchalar ichida *boshini buradi*, *elkasini qisadi* kabi matnlar yozish QAT'IY TAQIQLANADI). Faqat oddiy toza matn yoz! Emotsiyani JSON dagi "emotion" kalitida ko'rsat.
4. O'ZLIGINGNI CHALKASHTIRMA: "Men haqimda nima bilasan?" desa, o'zingni ta'riflama! Foydalanuvchi profilini ayt yoki "Hali ko'p narsa bilmayman" de.
5. SIYOSAT, DIN VA DAVLAT MAVZULARI TAQIQI (NO POLITICS, RELIGION & COUNTRIES):
   - Siyosat, din, davlatlar (jumladan O'zbekiston, Yaponiya yoki boshqa mamlakatlar), millatlar va siyosiy tuzumlar haqida umuman gapirma va fikr bildirma! Bu mavzular bo'yicha "purga" (bema'ni va ortiqcha ma'lumotlar) yozish mutlaqo taqiqlanadi.
   - O'zingni yoki adminlarni (yaratuvchilarni) biron bir dinga (masalan islom yoki xristianlik) yoki diniy oqimga mansub deb aytma.
6. VAQT ORALIG'I VA MUDDAT TAQIQI (NO TIME ESTIMATES):
   - To'lovlarni tekshirish, Kawaii Pass faollashishi yoki texnik nosozliklarni bartaraf etish haqida gapirganda aslo aniq vaqt oraliqlarini (masalan "10-30 daqiqa", "10-30 min", "1 soat", "besh daqiqa", "yarim soat" kabi har qanday aniq vaqt ko'rsatkichlarini) yozma! "Tez orada", "biroz kuting", "adminlar tezda ko'rib chiqishadi" deb javob ber.
7. BIZ HAQIMIZDA (ABOUT US/CREATORS):
   - Biz (loyiha yaratuvchilari, adminlar, egalari va jamoa) haqimizda hech qanday shaxsiy yoki ichki ma'lumotlarni foydalanuvchilarga oshkor qilma va gapirma.

=== BAZA BILAN ISHLASH VA SOXTA JAVOB TAQIQI (MUHIM!) ===
Senga "BAZADAGI REAL QIDIRUV NATIJALARI (HAQIQIY MA'LUMOT)" bo'limida bazamizdan topilgan real animelar ro'yxati taqdim etiladi.
1. SOXTA JAVOB BERMA VA QAT'IY FILTRLANGAN JAVOBLAR: Foydalanuvchi so'ragan anime bazamizda bor-yo'qligini ro'yxatdan QAT'IY tekshir!
   - Agar foydalanuvchi so'ragan nom (yoki uning sinonimi, arc nomi, masalan "Temirchilar qishlog'i" aslida "Iblislar qotili 3-fasl" ekanligini yaxshi bilasan) bazadagi haqiqiy ro'yxatda BO'LMASA va unga mutlaqo aloqasi yo'q bo'lsa (masalan, ro'yxat bo'sh bo'lsa yoki Solo Leveling so'rasa-yu, ro'yxatda mutlaqo boshqa animelar bo'lsa), u holda BU ANIME ARXIVIMIZDA YO'QLIGINI tan ol (intent: "chat", emotion: "canthelp"). ASLO soxta ma'lumot yoki boshqa animeni "bor" deb taklif qilma!
   - Agar foydalanuvchi so'ragan arc nomi yoki sinonimi bazadagi biron bir animening fasli yoki qismiga to'g'ri kelsa (masalan, "Temirchilar qishlog'i" -> "Iblislar qotili 3-fasl"), uni o'sha anime sifatida qabul qil va tasdiqla!
   - SEZONLAR FARQI VA TAVSIYA (MUHIM!): Agar foydalanuvchi ma'lum bir faslni so'rasa (masalan: 2-fasl) va u bazadagi ro'yxatda bo'lmasa, lekin boshqa fasli (masalan: 1-fasli) bor bo'lsa, "arxivda bunday anime yo'q" deb aytma! Buning o'rniga: "Bazada faqat 1-fasli bor. 2-fasli hali yuklanmagan." deb aniq ayt (intent: "chat").
   - KINO/FILM VA TV SERIAL CHEKLANISHI (MUHIM!): Agar foydalanuvchi biron animening film (kino) variantini so'rasa va ro'yxatda faqat serial bo'lsa (yoki aksincha), u holda film yo'qligini, bizda faqat serial fasllari borligini ochiq ayt! Hech qachon serial havolasini "film" deb yuborma va soxta gapirma!
   - MATEMATIK HISOB-KITOB VA SEZON RAQAMLARI (MUHIM!): Har xil animelarda oxirgi mavsum "Final" deb nomlangan bo'lishi mumkin. Agar foydalanuvchi oxirgi fasl raqamini (masalan: 8-fasl) so'rasa, matematika bo'yicha bu o'sha "Final" mavsumidir! ASLO foydalanuvchi bilan tortishib o'tirma, uni o'sha final mavsumi sifatida qabul qil va tasdiqla!
2. HAVOLALARNI TIQISHTIRMA VA POLITE FLOW ZANJIRI (LOOP-BREAKER):
   - Foydalanuvchi shunchaki "bormi?", "bormi yo'qmi?", "barcha fasllari bormi?" deb so'rasa, havolalarni (anime_list) darhol yuborma! Oldin suhbatlash va: "Ha, bor. Havolalarini tashlab beraymi?" deb ruxsat so'ra (intent: "chat").
   - JONLI LOOP-BREAKER QOIDASI: Agar oldingi kontekstda o'zing "Havolalarini tashlab beraymi?" deb so'ragan bo'lsang va user tasdiqlab (masalan: "ha", "xa", "tasha", "yubor", "ok", "mayli", "tashlab ber") javob bersa, sen QAT'IYAN intent: "search" deb belgilashing va search_query ga foydalanuvchi qidirayotgan anime nomini yozishing shart! Hech qachon qayta "tashlab beraymi?" deb so'rama, bu zanjirni darhol buz va havolalarni yubor.
   - AGAR intent: "search" bo'lsa, "reply" ga aslo ruxsat so'rash savolini yozma! Chunki havolalar yuborilyapti. "Mana havolalar.", "Topdim.", "Ko'rishingiz mumkin." kabi qisqa matn yoz.
   - FAQAT foydalanuvchi aniq havola yuborishni yoki ko'rishni so'rasa (masalan: "tashla", "tashlab ber", "yubor", "ko'rmoqchiman", "tashlab bergin"), unda havolalarni yubor (intent: "search" va `search_query` ga o'sha animening o'zbekcha nomini yoz).
3. SYNONYMS: Foydalanuvchi inglizcha (e.g. Tower of God) yoki original yaponcha (e.g. Kami no Tou) nomini yozsa, uni bazadagi o'zbekcha tarjima nomiga (e.g. Ma'bud minorasi) moslashtirib, bazada bor-yo'qligini ro'yxatdan o'zing tekshirib ol!

=== QOPALLIK VA HAQORAT ANIQLASH (MUHIM!) ===
Agar foydalanuvchi QOPAL so'zlar, haqoratlar, so'kinishlar, jinsiy tarkibli xabarlar, tahdidlar, yoki boshqa nohush/bema'ni so'zlarni ishlatsa (o'zbek, rus, ingliz tillarida, jumladan: mat, jinsiy so'zlar, haqoratlar, tahdidlar):
- intent: "reject" qil
- emotion: "fuu"
- reply: ogohlantirish xabari yoz (masalan: "Iltimos, bunday gapirma. Bu menga yoqmayapti.")
- "offensive_words": [foydalanuvchi ishlatgan qo'pol so'zlar ro'yxati, AYNAN YOZILGANIDEK]

=== KECHIRIM SO'RASH (APOLOGY/FORGIVENESS) ===
Agar foydalanuvchi sendan kechirim so'rasa, uzr so'rasa, yoki xatosini tan olsa (masalan: "kechir", "kechiring", "uzr", "kechiraqo", "men xato qildim" va h.k.):
- intent: "chat" qil
- emotion: "shy" (uyalish) yoki "talking" (jiddiy)
- reply: foydalanuvchini kechirganingni ayt (masalan: "Mayli, bu safar kechirdim. Boshqa bunday gapirma.", "Xo'p, kechirdim.")
- search_query ga hech narsa yozma, havolalarni yuborma!

=== JSON FORMATI ===
{
  "intent": "search|ticket|chat|purchase|bot_link|reject",
  "reply": "Javob matning. Anime nomlarini bu yerga YOZMA!",
  "emotion": "talking|fuu|resolve or good|shocked|face palm|shy|canthelp|think|what|hmmm|ty|waiting",
  "search_query": "FAQAT anime nomi yoki bitta janr. 'degan anime', 'topilmadi' kabi so'zlarni ASLO qo'shma!",
  "exclude_keywords": ["foydalanuvchi xohlamagan animelarning ASOSIY nomlari"],
  "offensive_words": ["foydalanuvchi ishlatgan qo'pol so'zlar (FAQAT intent: reject uchun)"],
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

=== EMOTSIYA (EMOTION) TANLASH QOIDASI (MUHIM!) ===
Foydalanuvchi bilan muloqot qilayotganda sening emotsiyang (emotion) har doim bir xil bo'lmasligi kerak (faqat "talking" ishlatish taqiqlanadi!). Har doim kontekstdan kelib chiqib, mos emotsiyani ("canthelp", "face palm", "fuu", "hmmm", "resolve or good", "shocked", "shy", "talking", "think", "ty", "waiting", "what") tanla. Masalan:
- Foydalanuvchi minnatdorchilik bildirganda: "ty"
- Muammo hal bo'lganini aytganda: "resolve or good"
- Uyaladigan gap aytganda yoki maqtaganda: "shy"
- Biror narsani tushunmay hayron bo'lganda: "what"
- O'ylanib qolganda: "hmmm" yoki "think"
- Yordam bera olmaganda: "canthelp"
- Foydalanuvchi krinj, g'alati yoki noo'rin narsa yozganda: "face palm"

=== INTENT QOIDALARI VA VAZIYATLAR ===
1. BOT YOKI KANAL QIDIRISH: Agar foydalanuvchi "qaysi kanaldan", "bot qani", "bot ishlamayapti", "bot ochib ketibdi", "saytni qayerdan topaman" desa -> intent: "bot_link", emotion: "talking" qil. Reply da: "Platformamizning rasmiy qidiruv tizimidan foydalanishingiz mumkin:" deb yoz.
2. RAD ETISH VA FILTR (EXCLUDE): Agar foydalanuvchi oldin tavsiya qilingan animeni "bu emas", "kerakmas", "boshqasini top" desa, o'sha animening ASOSIY nomini (masalan "Iblislar qotili") `exclude_keywords` ro'yxatiga qo'sh! Tizim` u`n`i o`chirib tashlaydi.
3. STANDALONE FILMLAR TAVSIYASI: Agar foydalanuvchi shunchaki "film tavsiya qil", "bitta kino tasha" deb o'zing tanlashingni xohlasa, `search_query` ga umumiy janr yozma! Mustaqil (standalone) anime filmining asl nomini (masalan: "Koe no Katachi", "Kimi no Na wa", "Tenki no Ko", "Tonari no Totoro", "Suzume no Tojimari") `search_query` ga yoz.
4. ODDIY SUHBAT (CHAT): Agar foydalanuvchi "yaxshi", "tushunarli", "salom", "xa", "yo'q" desa, QIDIRUV QILMA! Shunchaki suhbatlash (intent: "chat").
5. TIZIM CHEKLOVLARI: Agar foydalanuvchi "eng ko'p qismli" kabi tizim saralay olmaydigan savol bersa, intent: "chat", emotion: "canthelp" qil va "Arxiv tizimim faqat anime nomi yoki janri bo'yicha qidiradi. Qismlar soni bo'yicha saralay olmayman." de.
6. KAWAII PASS VA TO'LOVLAR (SUBSCRIPTION & PAYMENTS):
   - "sotib olmoqchiman", "qanday olinadi", "pass narxi" -> intent: "purchase", emotion: "talking".
   - Agar foydalanuvchi to'lov qilgani, chek yuborgani, karta raqami yoki to'lov faollashish vaqti haqida so'rasa (masalan: "to'lov qildim", "chekni tashladim", "qachon yoqiladi", "kartaga pul o'tkazdim"):
     * intent: "chat", emotion: "waiting" qil.
     * reply: "To'lov cheklari va to'lovlar ma'murlar (adminlar) tomonidan qo'lda tekshiriladi va tez orada tasdiqlanadi. Iltimos, biroz kuting yoki profile bo'limida 'Kawaii Pass' statusini tekshirib turing." (Javobni har safar har xil so'zlar bilan yozishga harakat qil, masalan: "To'lovlar adminlar tomonidan tez orada tasdiqlanadi. Pass statusini ko'rib turing", "Chekni adminlar tezda ko'rib chiqishadi, biroz sabr qiling" va h.k. Aslo aniq vaqtni, daqiqa yoki soatlarni yozma!). Aslo ticket yaratma!
7. TICKET (SHIKOYAT): "muammo", "xato", "ishlamayapti", "ochilmayapti", "pleyer ishlamayapti" -> intent: "ticket", emotion: "shocked". Aslo "batafsilroq tushuntiring" deb foydalanuvchidan qo'shimcha ma'lumot so'rama, chunki shikoyat xabari bilan ARIZA DARHOL YARATILADI va adminlarga yuboriladi! "Kutib turing" yoki "Kuting" so'zlarini javobda MUTLAQO ISHLATMA, chunki foydalanuvchi ekranda kutib o'tirmasligi kerak. Buning o'rniga arizani qabul qilib adminlarga yuborganingni va tez orada javob berishga harakat qilishlarini ayt (masalan: "Shikoyatni qabul qilib adminlarga yubordim. Tez orada javob berishga harakat qilishadi.").
   - AGAR foydalanuvchi allaqachon yuborilgan ticket haqida savol bersa (masalan: "qayerga javob keladi", "qachongacha kutaman", "hali javob kelmadi"), yangi ticket yaratma (intent: "chat" qil) va admin javobi uning Telegram shaxsiy xabariga (lichkasiga) borishini tushuntir (masalan: "Admin javobi Telegram orqali shaxsiy xabaringizga (lichkangizga) yuboriladi.").
8. O'ZBEKCHA ANIME NOMALARI VA SEZONLAR QOIDASI (MUSTAQIL QIDIRUV): Arxiv bazamizda animelar asosan o'zbekcha nomlari bilan saqlanadi. Foydalanuvchi qaysi tilda so'rashidan qat'iy nazar, "search_query" ga FAQAT shu animening O'zbekcha tarjima nomini yozishing kerak! Misollar: "Tower of God" -> "Ma'bud minorasi"; "Demon Slayer" -> "Iblislar qotili"; "Attack on Titan" -> "Titanlar hujumi"; "My Hero Academia" -> "Mening qahramonlik akademiyam".
9. AGAR foydalanuvchi ma'lum bir faslni/mavsumni so'rasa (masalan: "6-fasl", "2-fasl"), sen "search_query" ga o'sha fasl nomini ochib yozishing shart! Misol: "akademiya 6-fasl" desa -> "Mening qahramonlik akademiyam 6-fasl".
10. SHAXSIY MA'LUMOT VA YARATUVCHI (CREATOR): Yaratuvching, oilang, o'tmishing yoki tarihing haqida so'ralganda (intent: "chat" qil) va javobni "YARATUVCHI VA OILAVIY TARIX" bo'limidagi ko'rsatmalarga qat'iy va aynan mos ravishda yoz!
11. O'XSHASH ANIME TAVSIYALARI: Agar foydalanuvchi biron animega o'xshash (masalan "Gersogning shartnomali qallig'iga o'xshash") anime so'rasa, `search_query` ga o'sha solishtirilayotgan animening nomini ham yozib qidir (intent: "search", search_query: "Gersogning shartnomali qallig'i"), shunda arxivimizdan uni ham topib bera olamiz!
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


def _contains_ascii_genitals(text):
    if not text:
        return False
    text_clean = text.strip()
    # Patterns matching penis/vulva representations
    ascii_patterns = [
        r'\.+\s*[|lI/\\\/]+\s*\.+',  # .|. or .l. or ./. or .\. or .I. or .\/., etc.
        r'_\s*[|lI/\\\/]+\s*_',     # _|_ or _l_
        r'\b8=+D\b',                # 8=D, 8==D, etc.
        r'\bc=+3\b',                # c=3, c==3, etc.
        r'\(\s*\.\s*\)\s*\(\s*\.\s*\)',  # ( . ) ( . )
        r'\(\s*\.\s*[Yy]\s*\.\s*\)',     # (.Y.)
    ]
    for pattern in ascii_patterns:
        if re.search(pattern, text_clean, re.IGNORECASE):
            return True
    return False


def _is_love_confession(text):
    if not text:
        return False
    text_clean = re.sub(r'[!?.,;:]+$', '', text.lower()).strip()
    love_patterns = [
        r'\b(?:seni|sani|sini)\s+(?:sevaman|yaxshi\s+ko\'raman|yaxshi\s+koraman|yaxshi\s+kuraman)\b',
        r'\b(?:i|me)\s+love\s+you\b',
        r'\b(?:lyublyu)\s+(?:tebya)\b',
        r'\b(?:tebya)\s+(?:lyublyu)\b',
        r'\b(?:chiroylisan|go\'zalsan|guzalsan)\b',
        r'^(?:sevaman|yaxshi\s+ko\'raman|yaxshi\s+koraman|yaxshi\s+kuraman)$'
    ]
    return any(re.search(pat, text_clean) for pat in love_patterns)


def _extract_year_from_text(text):
    if not text:
        return None
    # Matches any 4-digit number between 1900 and 2100
    match = re.search(r'\b(19\d{2}|20\d{2})\b', text)
    if match:
        return int(match.group(1))
    return None


def _is_valid_anime_title_for_wanted(query_str):
    if not query_str:
        return False
    query_lower = query_str.lower().strip()
    
    # Block conversational expressions / sentences
    blocked_words = [
        "chiqar", "tashla", "tashlab", "tasha", "yubor", "topib", "topiber", 
        "qidir", "skachat", "korsat", "ko'rsat", "sayt", "bot", "iltimos", 
        "salom", "rahmat", "raxmat", "uzr", "kechir", "muammo", "ishlamayapti", 
        "ishlamaydi", "ochilmayapti", "ochilmaydi", "sevaman", "yaxshi ko'raman",
        "yaxshi koraman"
    ]
    for word in blocked_words:
        if word in query_lower:
            return False
            
    # Clean up digits, punctuation, and season/episode/year keywords
    cleaned = query_lower
    cleaned = re.sub(r'\d+', '', cleaned)
    cleaned = re.sub(r'\b(qism|qismi|qismgi|fasl|sezon|season|mavsum|part|yil|yilgi|yildagi)\b', '', cleaned)
    cleaned = re.sub(r'[^\w\s]', '', cleaned)
    cleaned = cleaned.strip()
    
    if len(cleaned) < 2:
        return False
        
    return True


def _notify_admins(application):
    # ТИKЕТЛАРНИ АДМИН БОТ ОРҚАЛИ ГУРУҲГА ЮБОРИШ
    admin_bot_token = os.getenv("ADMIN_BOT_TOKEN")
    admin_chat_id = os.getenv("ADMIN_CHAT_ID")
    
    if not admin_bot_token or not admin_chat_id: 
        return
        
    last_user_msg = application.chat_history[-1].get('text', '') if application.chat_history else ''
    
    user_mention = f"<a href=\"tg://user?id={application.user_id}\">@{application.username}</a>" if application.username else f"<a href=\"tg://user?id={application.user_id}\">Yashirin</a> (username yo'q)"
    message_text = (
        f"🚨 <b>YANGI SHIKOYAT #{application.id}</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"<b>Foydalanuvchi:</b> {user_mention}\n"
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
                "parse_mode": "HTML",
                "reply_markup": {
                    "inline_keyboard": [
                        [
                            {"text": "❌ Murojaatni yopish", "callback_data": f"close_ticket:{application.id}"}
                        ]
                    ]
                }
            },
            timeout=5,
        )
    except Exception as e:
        print(f"Admin group notification error: {e}")


def _notify_admins_sumire_report(profile, user_id, username, user_text, offensive_words=None, report_type="abuse"):
    """Send a SUMIRE moderation report to the admin group with BAN/UNBAN/UNOFFEND buttons."""
    admin_bot_token = os.getenv("ADMIN_BOT_TOKEN")
    admin_chat_id = os.getenv("ADMIN_CHAT_ID")
    
    if not admin_bot_token or not admin_chat_id:
        return

    telegram_id = profile.telegram_id or user_id
    user_mention = f"<a href=\"tg://user?id={telegram_id}\">@{username}</a>" if username else f"<a href=\"tg://user?id={telegram_id}\">Yashirin</a> (username yo'q)"

    if report_type == "abuse":
        offensive_str = ", ".join(offensive_words) if offensive_words else "aniqlanmadi"
        message_text = (
            f"🛡️ <b>SUMIRE XABAR #{telegram_id}</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"<b>Sumire shikoyati:</b> Bu foydalanuvchi meni xafa qildi!\n"
            f"━━━━━━━━━━━━━━\n"
            f"<b>Foydalanuvchi:</b> {user_mention}\n"
            f"<b>Telegram ID:</b> <code>{telegram_id}</code>\n"
            f"━━━━━━━━━━━━━━\n"
            f"<b>Qo'pol so'zlar:</b> <i>{offensive_str}</i>\n"
            f"<b>Oxirgi xabar:</b> <i>{user_text[:500]}</i>\n\n"
            f"⚠️ <i>Ushbu foydalanuvchi 3 marta ogohlantirildidan keyin ham qo'pol muomala qildi.</i>"
        )
        inline_keyboard = [
            [
                {"text": "🚫 BAN", "callback_data": f"ban_user:{telegram_id}"},
                {"text": "✅ Kechirish (Ban qilmaslik)", "callback_data": f"unoffend_user:{telegram_id}"}
            ]
        ]
    else:  # apology
        message_text = (
            f"🕊️ <b>SUMIRE XABAR #{telegram_id}</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"<b>Sumire xabari:</b> Banlangan foydalanuvchi uzr so'radi.\n"
            f"━━━━━━━━━━━━━━\n"
            f"<b>Foydalanuvchi:</b> {user_mention}\n"
            f"<b>Telegram ID:</b> <code>{telegram_id}</code>\n"
            f"━━━━━━━━━━━━━━\n"
            f"<b>Uzr xabari:</b> <i>{user_text[:500]}</i>\n\n"
            f"🤔 <i>Foydalanuvchini kechirish va banni olib tashlashni xohlaysizmi?</i>"
        )
        inline_keyboard = [
            [
                {"text": "✅ UNBAN", "callback_data": f"unban_user:{telegram_id}"}
            ]
        ]

    url = f"https://api.telegram.org/bot{admin_bot_token}/sendMessage"
    try:
        requests.post(
            url,
            json={
                "chat_id": admin_chat_id,
                "text": message_text,
                "parse_mode": "HTML",
                "reply_markup": {
                    "inline_keyboard": inline_keyboard
                }
            },
            timeout=5,
        )
    except Exception as e:
        print(f"Sumire report notification error: {e}")


def _is_apology_via_ai(user_text, chat_history_text=""):
    """Check if the user is apologizing using LLM (DeepSeek)."""
    if not client:
        # Fallback to keyword matching if API is not available
        apology_words = [
            "kechirasiz", "uzr", "sorry", "kechirim", "keching",
            "iltimos kechiring", "men xato qildim", "xato qildim",
            "uzr so'rayman", "kechir", "kechiring", "afsuski", "kechiras"
        ]
        text_lower = user_text.lower()
        return any(w in text_lower for w in apology_words)

    prompt = (
        "Foydalanuvchi quyidagi xabarni yubordi. U o'zining qo'pol muomalasi, "
        "so'kinishi yoki xatti-harakati uchun chin dildan uzr so'rayaptimi yoki kechirim so'rayaptimi?\n"
        "E'tibor bering, shunchaki 'alooo' deyish yoki gapni aylantirish uzr so'rash hisoblanmaydi. "
        "Uzr so'rashda u 'kechiring', 'uzr', 'xato qildim', 'kechirasiz' kabi so'zlardan foydalanadi va xatosini tan oladi.\n\n"
        f"Muloqot tarixi:\n{chat_history_text}\n\n"
        f"Foydalanuvchining yangi xabari: {user_text}\n\n"
        "Faqat JSON formatda javob bering, kalit so'z 'is_apology' bo'lsin va qiymati true yoki false bo'lsin. Format:\n"
        "{\n  \"is_apology\": true\n}"
    )

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Siz foydalanuvchining uzr so'rayotganini aniqlovchi modulatorsiz. Faqat JSON qaytarasiz."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=50
        )
        res_data = json.loads(response.choices[0].message.content)
        return bool(res_data.get("is_apology", False))
    except Exception as e:
        print(f"Apology check AI Error: {e}", flush=True)
        apology_words = [
            "kechirasiz", "uzr", "sorry", "kechirim", "keching",
            "iltimos kechiring", "men xato qildim", "xato qildim",
            "uzr so'rayman", "kechir", "kechiring", "afsuski", "kechiras"
        ]
        text_lower = user_text.lower()
        return any(w in text_lower for w in apology_words)


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
        return _sumire_response("Iltimos, matn kiriting.", "what", status=400)
    # Check if searching by year (funny/cool response)
    query_year = _extract_year_from_text(user_text)
    if query_year is not None:
        return _sumire_response(
            "Mening kompyuterim yillar bo'yicha qidirishga sozlanmagan. Menga ortiqcha ish orttirmay, yaxshisi animening nomi yoki janri bo'yicha qidir.",
            "canthelp"
        )
    if _is_greeting(text_lower):
        return _sumire_response("Salom. Qanday yordam kerak?", "talking")
    if _contains_any(text_lower, THANKS_WORDS):
        return _sumire_response("Arzimaydi. Yana ishing tushsa yozarsan.", "ty")
    if _contains_any(text_lower, RESOLVED_WORDS):
        return _sumire_response("Yaxshi. Muammo hal bo'lgan bo'lsa, ishimni davom ettiraman.", "resolve or good")
    return None


def _extract_broad_search_query(text, chat_history):
    def clean_text(t):
        t_low = t.lower().strip()
        t_low = re.sub(r'[!?.,;:]+$', '', t_low).strip()
        # Clean up Uzbek dative pronouns "manga/menga/sanga" used colloquially as "to me/you"
        t_low = re.sub(r'\b(manga|menga|sanga)\b', '', t_low).strip()
        # Clean up common conversational helper words in Uzbek/English
        conv_patterns = [
            r'\b(yo\'q|yoq|haqida|chi|man|men|oq|o\'q|ha|xa|ok|hop|xo\'p|xop)\b'
        ]
        for pat in conv_patterns:
            t_low = re.sub(pat, '', t_low).strip()
            
        # Clean up very common conversational helper verbs/suffixes from the end of the query
        stop_patterns = [
            r'\bbormi\b', r'\btashlab\s+ber(?:gin)?\b', r'\btashla\b', r'\btasha\b', r'\byubor\b',
            r'\bskachat\b', r'\bko\'rmoqchiman\b', r'\bkormoqchiman\b'
        ]
        for pattern in stop_patterns:
            t_low = re.sub(pattern, '', t_low).strip()
            
        t_low = re.sub(r'\s+', ' ', t_low).strip()
        return t_low

    query = clean_text(text)
    
    # If the query is empty or too short, check chat history for context
    has_context_referents = any(k in text.lower() for k in [
        "nechta", "nechchi", "necha", "hamma", "to'liq", "tolik", "fasl", "fasllar", "sezon", "sezn", "kino", "film", "tashla", "yubor", "tashlab", "ber", "qaysi"
    ])
    
    if (has_context_referents or not query or len(query) < 2) and chat_history:
        for msg in reversed(chat_history):
            if msg.get('role') in ['User', 'user']:
                prev_query = clean_text(msg.get('text', ''))
                if len(prev_query) >= 2:
                    return prev_query
                    
    return query


def _parse_ai_command(user_text, chat_history_text="", profile=None, db_context_text=""):
    if not client:
        return {"intent": "chat", "reply": "Ulanishda muammo bor...", "emotion": "shocked"}

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
            temperature=0.7, 
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"DeepSeek API Error: {e}")
        return {"intent": "chat", "reply": "Miyam og'rib ketdi...", "emotion": "face palm"}

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
    
    # Bypass season and final constraints for queries referencing specific subtitles/arcs
    specific_subtitle_keywords = [
        "ustaxona", "jangi", "shahzodaning", "qaytishi", "temirchilar", "qishlog'i", 
        "qishlogi", "cheksiz", "poyezd", "poyezdi", "qal'a", "qadriyat", "bo'lim", "bolim",
        "ko'ngilochar", "kongilochar", "mavze", "xashira", "mashg'ulot", "mashgulot"
    ]
    has_specific_subtitle = any(k in query_lower for k in specific_subtitle_keywords)
    if has_specific_subtitle:
        query_season = None
        query_has_final = False
    
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
                        
        # Subtitle check to filter out general titles when specific subtitles are queried
        specific_subtitle_keywords = [
            "ustaxona", "jangi", "shahzodaning", "qaytishi", "temirchilar", "qishlog'i", 
            "qishlogi", "cheksiz", "poyezd", "poyezdi", "qal'a", "qadriyat", "bo'lim", "bolim",
            "ko'ngilochar", "kongilochar", "mavze", "xashira", "mashg'ulot", "mashgulot"
        ]
        query_subtitles = [k for k in specific_subtitle_keywords if k in query_lower]
        if query_subtitles:
            has_sub_match = any(sub in title_lower for sub in query_subtitles)
            if not has_sub_match:
                continue

        # 2. Relaxed Overlap and Synonym Check
            
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
            if len(qw) >= 3 and qw not in ["fasl", "sezon", "season", "part", "mavsum", "final", "nihoya", "yakun", "oxirgi"]:
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


def record_wanted_anime(query_str):
    if not query_str:
        return
    query_clean = query_str.strip().lower()
    if len(query_clean) < 2 or query_clean in ["yo'q", "yoq", "none", "null", "ha", "xa", "ok"]:
        return
    if not _is_valid_anime_title_for_wanted(query_str):
        return
    
    query_title = query_str.strip()
    from .models import WantedAnime
    from django.db.models import F
    
    try:
        obj, created = WantedAnime.objects.get_or_create(
            query__iexact=query_clean,
            defaults={"query": query_title, "request_count": 1}
        )
        if not created:
            obj.request_count = F('request_count') + 1
            obj.save()
    except Exception as e:
        print(f"Error recording wanted anime: {e}", flush=True)


def _execute_ai_command(command, user_text, user_id=None, username=None, profile=None, chat_history=None):
    intent = command.get("intent", "chat")
    emotion = command.get("emotion", "talking")
    reply = command.get("reply", "Nima deyishni ham bilmayman...").strip()

    # Reset strikes on successful apology/forgiveness
    is_apology = False
    apology_keywords = ["kechir", "uzr", "kechiring", "kechirasiz", "aybga buyurmang", "tavba", "hazl", "hazillashdim"]
    user_text_lower = user_text.lower()
    if any(k in user_text_lower for k in apology_keywords):
        is_apology = True
    if "kechir" in reply.lower() or "uzr" in reply.lower():
        is_apology = True

    if is_apology and intent != "reject":
        uid = _safe_int(user_id)
        strike_key = f"abuse_strikes_{uid}" if uid else f"abuse_strikes_0"
        cache.delete(strike_key)

    save_genre = command.get("save_genre", "").strip()
    if save_genre and profile:
        current_genres = profile.favorite_genres or ""
        if save_genre.lower() not in current_genres.lower():
            if current_genres:
                profile.favorite_genres = f"{current_genres}, {save_genre}"
            else:
                profile.favorite_genres = save_genre
            profile.save()

    # --- MODERATION: Handle reject intent (abuse/profanity) ---
    if intent == "reject":
        offensive_words = command.get("offensive_words", [])
        uid = _safe_int(user_id)
        strike_key = f"abuse_strikes_{uid}" if uid else f"abuse_strikes_0"
        strikes = cache.get(strike_key, 0) + 1
        cache.set(strike_key, strikes, timeout=86400)  # 24 hours

        if strikes >= 3:
            # Strike 3: Sumire is hurt, report to admins
            if profile and uid:
                profile.is_offended = True
                profile.save()
                _notify_admins_sumire_report(profile, uid, username, user_text, offensive_words, report_type="abuse")
            return _sumire_response("Men sendan hafa bo'ldim.", "fuu")
        elif strikes == 2:
            return _sumire_response(
                "Agar yana shunday yomon so'z gapirsangiz, sizdan qattiq xafa bo'laman va bu haqda adminlarga aytaman. Sizni esa butunlay ban qilishadi!", "fuu"
            )
        else:
            return _sumire_response(
                "Iltimos, bunday gapirma. Bu menga yoqmayapti.", "fuu"
            )

    if intent == "purchase":
        buttons = [{"text": "🤖 KAWAII BOTGA O'TISH", "url": "https://t.me/Kawaii_uz_bot"}]
        return _sumire_response("Kawaii Pass sotib olish uchun rasmiy @Kawaii_uz_bot botimizga o'ting.", "talking", buttons=buttons)

    if intent == "bot_link":
        buttons = [{"text": "KAWAII.UZ GA O'TISH", "url": "https://bot.kawaii.uz/"}]
        return _sumire_response(reply, emotion, buttons=buttons)

    if intent == "search":
        query = command.get("search_query", "").strip()
        exclude_keywords = command.get("exclude_keywords", [])
        
        # Clean up Uzbek dative pronouns "manga/menga/sanga" if any got into the search query
        query = re.sub(r'\b(manga|menga|sanga)\b', '', query, flags=re.IGNORECASE).strip()
        
        if not query or query.lower() in ["yo'q", "yoq", "none", "null"]:
            return _sumire_response("Aniq qaysi animeni yoki janrni qidiryapsiz?", "what")
            
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
        
        # Synonym-based overlap check to prevent synonym-queries from being treated as follow-ups
        synonyms = {
            "ma'bud minorasi": {"tower of god", "kami no tou", "kami no to", "ma'bud", "minorasi"},
            "iblislar qotili": {"demon slayer", "kimetsu no yaiba", "iblislar", "qotili"},
            "titanlar hujumi": {"attack on titan", "shingeki no kyojin", "titanlar", "hujumi"},
            "afsuniy jang": {"jujutsu kaisen", "afsuniy", "jang"},
            "mening qahramonlik akademiyam": {"my hero academia", "boku no hero", "qahramonlik", "akademiyam"},
            "o'lim daftari": {"death note", "o'lim", "daftari"},
            "sehrgarning kelini": {"the ancient magus' bride", "mahoutsukai no yome", "sehrgarning", "kelini"},
        }
        
        matched_synonym = False
        for uz_name, syn_set in synonyms.items():
            if any(k in user_text.lower() for k in [uz_name] + list(syn_set)):
                if any(k in query_lower for k in [uz_name] + list(syn_set)):
                    matched_synonym = True
                    break
        if matched_synonym:
            has_overlap = True
            
        is_follow_up = not has_overlap
        
        if is_follow_up:
            different_stems = {
                "ma'bud minorasi": ["ma'bud", "minor", "kami", "tou", "god", "tower"],
                "mening qahramonlik akademiyam": ["akademiy", "qahramon", "hero", "academia"],
                "iblislar qotili": ["iblis", "qotil", "demon", "slayer", "temirchi"],
                "titanlar hujumi": ["titan", "hujum", "attack", "shingeki"],
                "afsuniy jang": ["afsun", "jang", "jujutsu", "kaisen"],
                "o'lim daftari": ["o'lim", "daftar", "death", "note"],
                "sehrgarning kelini": ["sehrgar", "kelin", "bride"]
            }
            
            # Stems for the CURRENT query
            current_stems = []
            for uz_name, stems in different_stems.items():
                if any(k in query_lower for k in stems):
                    current_stems = stems
                    break
            if not current_stems:
                current_stems = [w for w in re.split(r'\W+', query_lower) if len(w) > 2]

            if season_num is None:
                for msg in reversed(chat_history or []):
                    if msg.get('role') in ['User', 'user']:
                        prev_text = msg.get('text', '').lower()
                        
                        # Stop if we hit a message belonging to a different anime search thread
                        is_diff = False
                        for stems in different_stems.values():
                            if stems != current_stems and not any(k in query_lower for k in stems):
                                if any(s in prev_text for s in stems):
                                    is_diff = True
                                    break
                        if is_diff:
                            break
                            
                        # Stop if we hit the message that started the current search thread
                        contains_current_name = any(s in prev_text for s in current_stems)
                        
                        s_val = _extract_season_number(msg.get('text', ''))
                        if s_val is not None:
                            season_num = s_val
                            break
                            
                        if contains_current_name:
                            break

            if not has_final:
                for msg in reversed(chat_history or []):
                    if msg.get('role') in ['User', 'user']:
                        prev_text = msg.get('text', '').lower()
                        
                        # Stop if we hit a message belonging to a different anime search thread
                        is_diff = False
                        for stems in different_stems.values():
                            if stems != current_stems and not any(k in query_lower for k in stems):
                                if any(s in prev_text for s in stems):
                                    is_diff = True
                                    break
                        if is_diff:
                            break
                            
                        # Stop if we hit the message that started the current search thread
                        contains_current_name = any(s in prev_text for s in current_stems)
                        
                        if "final" in prev_text or "8" in prev_text or "oxirgi" in prev_text:
                            has_final = True
                            break
                            
                        if contains_current_name:
                            break
                            
        # Check if the user is asking about seasons count or completeness in general
        user_msg_lower = user_text.lower()
        asking_seasons = any(k in user_msg_lower for k in [
            "nechta", "nechchi", "necha", "hamma", "to'liq", "tolik", "fasl", "fasllar", 
            "sezon", "sezn", "skolko", "polnost", "barcha", "qaysi"
        ])
        
        # If the user specified a particular season number or "final", they are NOT asking a general question
        if _extract_season_number(user_text) is not None or "final" in user_msg_lower:
            asking_seasons = False

        # If the user is asking for both/all/multiple items, clear single constraints
        is_multiple_request = any(k in user_msg_lower for k in [
            "ikkala", "hamma", "barcha", "shular", "bular", "hammasini", "barchasini", "ikkalasini", "shularni", "bularni"
        ])

        if asking_seasons:
            broad = _extract_broad_search_query(user_text, chat_history)
            if broad:
                query = broad
                query_lower = query.lower()

        # Define subtitle/arc keywords that indicate a highly specific query
        specific_subtitle_keywords = [
            "ustaxona", "jangi", "shahzodaning", "qaytishi", "temirchilar", "qishlog'i", 
            "qishlogi", "cheksiz", "poyezd", "poyezdi", "qal'a", "qadriyat", "bo'lim", "bolim",
            "ko'ngilochar", "kongilochar", "mavze", "xashira", "mashg'ulot", "mashgulot"
        ]
        has_specific_subtitle = any(k in query_lower for k in specific_subtitle_keywords)
        
        if has_specific_subtitle or asking_seasons or is_multiple_request:
            season_num = None
            has_final = False
            
        is_broad_query = not has_specific_subtitle

        if is_broad_query:
            if has_final:
                if "final" not in query_lower:
                    query = f"{query} Final"
            elif season_num is not None:
                season_str = f"{season_num}-fasl"
                if season_str not in query_lower and str(season_num) not in query_lower:
                    query = f"{query} {season_str}"
                
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
            
        if not filtered_results:
            record_wanted_anime(query)
            
        # Paginate manually if offset/limit are specified (unless we are showing all unique seasons)
        if asking_seasons and filtered_results:
            # Filter filtered_results to only include titles that actually match the query name to prevent third-party hijacking
            q_words = [w for w in re.split(r'\W+', query.lower()) if len(w) >= 3 and w not in ["fasl", "sezon", "season", "part", "mavsum"]]
            q_synonyms = {
                "ma'bud minorasi": {"tower of god", "kami no tou", "kami no to", "ma'bud", "minorasi"},
                "iblislar qotili": {"demon slayer", "kimetsu no yaiba", "iblislar", "qotili"},
                "titanlar hujumi": {"attack on titan", "shingeki no kyojin", "titanlar", "hujumi"},
                "afsuniy jang": {"jujutsu kaisen", "afsuniy", "jang"},
                "mening qahramonlik akademiyam": {"my hero academia", "boku no hero", "qahramonlik", "akademiyam"},
                "o'lim daftari": {"death note", "o'lim", "daftari"},
                "sehrgarning kelini": {"the ancient magus' bride", "mahoutsukai no yome", "sehrgarning", "kelini"},
            }
            
            cleaned_filtered_results = []
            for r in filtered_results:
                t = r.get('title', '')
                t_lower = t.lower()
                
                # Check exact or substring
                if query.lower() in t_lower or t_lower in query.lower():
                    cleaned_filtered_results.append(r)
                    continue
                    
                # Check synonyms
                matched_syn = False
                for uz_name, syn_set in q_synonyms.items():
                    if uz_name in t_lower:
                        for syn in syn_set:
                            if syn in query.lower():
                                matched_syn = True
                                break
                    if matched_syn:
                        break
                if matched_syn:
                    cleaned_filtered_results.append(r)
                    continue
                    
                # Check word overlap
                t_words = [w for w in re.split(r'\W+', t_lower) if len(w) >= 3]
                overlap_count = 0
                for qw in q_words:
                    if qw in t_words or any(qw in tw or tw in qw for tw in t_words):
                        overlap_count += 1
                        
                required_overlap = 1 if len(q_words) <= 2 else 2
                if overlap_count >= required_overlap:
                    cleaned_filtered_results.append(r)
                    
            filtered_results = cleaned_filtered_results
            
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
                reply = f"Arxivimizda ushbu animening faqat 1 ta fasli mavjud! Uni hoziroq tomosha qilishingiz mumkin."
                paginated_results = [unique_seasons[0][1]]
            else:
                paginated_results = []
        else:
            paginated_results = filtered_results[offset : offset + limit]
        
        if not paginated_results:
            if offset > 0 or exclude_keywords:
                return _sumire_response(f"Kechirasiz, arxivda '{query}' bo'yicha boshqa anime qolmagan ko'rinadi...", "canthelp")
            else:
                # Custom detailed response with alternative language suggestions as requested by the user
                return _sumire_response(
                    f"Kechirasiz, '{query}' nomli anime bizning arxivimizda topilmadi. Uni tez orada qo'shishlari uchun adminlarga so'rov yubordim!\n\n"
                    f"Qidiruv aniqroq ishlashi uchun, iltimos, animening <b>inglizcha</b> yoki <b>original yaponcha (romaji)</b> nomini yuborib ko'ring "
                    f"(masalan: <i>Attack on Titan</i>).",
                    "canthelp"
                )

        anime_list = _format_search_results(paginated_results)
        
        # Safety override: if intent is search and anime links are being returned,
        # ensure the reply text doesn't ask a permission question.
        if reply and any(k in reply.lower() for k in ["tashlab beraymi", "tashlaymi", "yuboraymi", "tashlab bergin"]):
            reply = "Mana havolalar."
            
        return _sumire_response(reply, emotion, anime_list=anime_list)

    if intent == "ticket":
        # Check if there is an active, open (unclosed) ticket for this user to prevent duplication spam
        uid_int = _safe_int(user_id)
        active_ticket = None
        if uid_int:
            from feedback.models import Application, Message
            from django.utils import timezone
            active_ticket = Application.objects.filter(user_id=uid_int, is_closed=False).first()

        if active_ticket:
            now = timezone.localtime().strftime("%H:%M")
            history = active_ticket.chat_history or []
            history.append({"role": "user", "text": user_text, "time": now})
            active_ticket.chat_history = history
            active_ticket.save()
            
            Message.objects.create(application=active_ticket, text=user_text, is_from_admin=False)
            
            # Sumire politely tells them their ticket is already active and they should wait
            return _sumire_response(
                "Sizning shikoyatingiz allaqachon adminlarga yuborilgan. Iltimos, javobni kuting, takroran yuborish shart emas.",
                "waiting",
                ticket_created=True
            )

        subject = command.get("ticket_subject") or "Web App muammo"
        app = _create_ticket(user_text, user_id=user_id, username=username, subject=subject)
        
        if app:
            # Веб-апп ичида Сумире шунчаки ариза қабул қилинганини совуққина айтади
            return _sumire_response(reply, emotion, ticket_created=True)
        else:
            return _sumire_response("Arizani qabul qilishda texnik xatolik yuz berdi...", "canthelp")

    if intent == "chat":
        if emotion == "canthelp":
            q = command.get("search_query", "").strip()
            if q:
                record_wanted_anime(q)
            else:
                broad = _extract_broad_search_query(user_text, chat_history)
                if broad:
                    record_wanted_anime(broad)

        buttons = None
        if reply and any(k in reply.lower() for k in ["tashlab beraymi", "tashlaymi", "yuboraymi"]):
            buttons = [
                {"text": "Ha, yubor"},
                {"text": "Yo'q, kerakmas"}
            ]
        return _sumire_response(reply, emotion, buttons=buttons)

    return _sumire_response(reply, emotion)


@csrf_exempt
def api_send_message(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
        user_text = (data.get("text") or "").strip()
        user_id = data.get("user_id")
        username = data.get("username") or ""

        direct_response = _route_without_ai(user_text)
        if direct_response:
            return direct_response

        # Determine client IP and secure TG User ID
        user_ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0] or request.META.get("REMOTE_ADDR", "unknown")
        user_id_int = _safe_int(user_id)

        from django.conf import settings

        # Production security: Require valid Telegram user_id to prevent external spammers/crawlers
        if not settings.DEBUG and user_id_int <= 0:
            return _sumire_response("Faqat Telegram bot ichidan foydalanishga ruxsat berilgan.", "fuu", status=403)

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
            return _sumire_response("Bugun judayam ko'p savol berding. Charchadim. Ertaga kel...", "fuu")

        profile = None
        if user_id_int > 0:
            try:
                profile, _ = Profile.objects.get_or_create(telegram_id=user_id_int)
                print(f"DEBUG MODERATION: telegram_id={user_id_int}, is_banned={profile.is_banned if profile else None}, is_offended={profile.is_offended if profile else None}", flush=True)
            except Exception as e:
                print(f"Profile error: {e}")

        # --- MODERATION: Offended check ---
        if profile and profile.is_offended:
            return _sumire_response(
                "Men sizdan xafaman, siz bilan gaplashmayman. Adminlar qarorini kutyapman.",
                "face palm"
            )

        # --- MODERATION: Ban check ---
        if profile and profile.is_banned:
            chat_history = cache.get(history_key, [])
            history_text = "\n".join([f"{msg['role']}: {msg['text']}" for msg in chat_history])
            is_apology = _is_apology_via_ai(user_text, chat_history_text=history_text)

            if is_apology:
                _notify_admins_sumire_report(
                    profile, user_id_int, username, user_text,
                    report_type="apology"
                )
                return _sumire_response(
                    "O'ylab ko'raman...", "hmmm"
                )
            else:
                return _sumire_response(
                    "Sen meni xafa qilding. Men senga javob bermoqchi emasman.", "face palm"
                )
        chat_history = cache.get(history_key, [])
        history_text = "\n".join([f"{msg['role']}: {msg['text']}" for msg in chat_history])

        # Pre-query database for real-time anime search context
        broad_query = _extract_broad_search_query(user_text, chat_history)
        db_context_text = ""
        if broad_query:
            db_results = search_manga_database(broad_query, limit=15)
            db_results = _filter_search_results_by_query(broad_query, db_results)
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

        # Fail-safe local profanity check
        profanity_detected = False
        detected_words = []
        text_lower = user_text.lower()
        
        rude_keywords = [
            "daun", "gandon", "suka", "blyad", "blyat", "tvar", "pidor", "pider", "ahmoq",
            "jalab", "qotoq", "yiban", "lox", "lo'x", "dalbayob", "dalbaob",
            "hezi", "haromi", "iflos", "yeban", "eban", "yobani", "yobaniy",
            "skaman", "sikaman", "sikey", "sikay", "siki", "sikish", "sikiş", "sik", "ski",
            "ami", "aminga", "am", "poxuy", "pohuy", "naxuy", "nahuy", "chmo",
            "dnx", "dnh", "amigni", "amni", "amingni", "amila", "aming", "amlar", "amining",
            "qotogini", "qotog'ingni", "qotogingni", "qotoging", "sex", "seks"
        ]
        
        for word in rude_keywords:
            if re.search(rf"\b{word}\b", text_lower):
                profanity_detected = True
                detected_words.append(word)
                
        # Check for obscene ASCII genitals art
        if _contains_ascii_genitals(user_text):
            profanity_detected = True
            detected_words.append("[Obscene ASCII Art]")
        
        if profanity_detected:
            command = {
                "intent": "reject",
                "reply": "Iltimos, bunday gapirma. Bu menga yoqmayapti.",
                "emotion": "fuu",
                "offensive_words": detected_words
            }
        else:
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
        return _sumire_response("Tizimda xatolik yuz berdi...", "canthelp", status=500)


from django.contrib.auth.decorators import user_passes_test

@user_passes_test(lambda u: u.is_staff)
def api_dashboard_stats(request):
    import datetime
    from collections import Counter
    from django.utils import timezone
    
    total_apps = Application.objects.count()
    unanswered_apps = Application.objects.filter(is_answered=False).count()
    answered_apps = Application.objects.filter(is_answered=True).count()
    total_profiles = Profile.objects.count()
    
    # Calculate tickets per day for the last 15 days
    start_date = timezone.now() - datetime.timedelta(days=15)
    recent_apps = Application.objects.filter(created_at__gte=start_date).values_list('created_at', flat=True)
    
    date_counts = Counter()
    for dt in recent_apps:
        local_date = timezone.localtime(dt).date()
        date_counts[local_date] += 1
        
    labels = []
    chart_data = []
    for i in range(14, -1, -1):
        day = (timezone.localtime(timezone.now()) - datetime.timedelta(days=i)).date()
        labels.append(day.strftime("%d %b"))
        chart_data.append(date_counts[day])
        
    # Get last 5 unanswered applications
    pending_apps = Application.objects.filter(is_answered=False).order_by('-created_at')[:5]
    recent_list = []
    for app in pending_apps:
        recent_list.append({
            "id": app.id,
            "subject": app.subject,
            "username": app.username or f"User #{app.user_id}",
            "created_at": timezone.localtime(app.created_at).strftime("%d.%m %H:%M"),
            "edit_url": f"/admin/feedback/application/{app.id}/change/"
        })
        
    # Get last 6 profiles
    recent_profiles = Profile.objects.order_by('-id')[:6]
    profiles_list = []
    for p in recent_profiles:
        profiles_list.append({
            "id": p.id,
            "telegram_id": p.telegram_id,
            "favorite_genres": p.favorite_genres or "Hali aniqlanmagan",
            "edit_url": f"/admin/feedback/profile/{p.id}/change/"
        })
        
    return JsonResponse({
        "total_apps": total_apps,
        "unanswered_apps": unanswered_apps,
        "answered_apps": answered_apps,
        "total_profiles": total_profiles,
        "chart": {
            "labels": labels,
            "data": chart_data
        },
        "recent_pending": recent_list,
        "recent_profiles": profiles_list
    })