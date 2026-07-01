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

ANIME_SYNONYMS = {
    "ma'bud minorasi": {"tower of god", "kami no tou", "kami no to", "ma'bud", "minorasi"},
    "iblislar qotili": {"demon slayer", "kimetsu no yaiba", "iblislar", "qotili", "клинок рассекающий демонов", "клинок"},
    "titanlar hujumi": {"attack on titan", "shingeki no kyojin", "titanlar", "hujumi", "атака титанов", "атаку титанов"},
    "jodugarlar jangi": {"jujutsu kaisen", "afsuniy jang", "jodugarlar", "jangi", "магическая битва", "магическую битву"},
    "mening qahramonlik akademiyam": {"my hero academia", "boku no hero", "qahramonlik", "akademiyam", "моя геройская академия"},
    "o'lim daftari": {"death note", "o'lim", "daftari", "тетрадь смерти"},
    "o'lim kundaligi": {"death note", "o'lim", "daftari", "kundaligi", "тетрадь смерти"},
    "sehrgarning kelini": {"the ancient magus' bride", "mahoutsukai no yome", "sehrgarning", "kelini"},
    "yolg'izlikda daraja ko'tarish": {"solo leveling", "solo level", "ore dake level up na ken", "ore dake", "level up", "соло левелинг", "соло левел", "yolgizlikda daraja kotarish", "yolgizlikda daraja ko'tarish", "yolg'izlikda daraja kotarish", "поднятие уровня в одиночку", "поднятие уровня"},
    "yulduz bolalari": {"oshi no ko", "oshinoko", "yulduz bolalari", "yulduz", "bolalari", "звездное дитя"},
    "sening isming": {"your name", "kimi no na wa", "kimi no nawa", "sening isming", "твое имя"},
    "yigit va qiz o'rtasida do'stlik bo'lishi mumkinmi!?": {"can a boy girl friendship survive", "danjo no yuujou wa seiritsu suru", "yigit va qiz", "o'rtasida do'stlik"},
    "daydi itlarning buyugi": {"bungou stray dogs", "bungo stray dogs", "великие из бродячих псов", "великие бродячие псы", "великих бродячих псов", "бродячие псы", "псы", "daydi itlarning buyugi", "daydi itlar", "buyuk sersuv itlar", "buyuk sarsonlar", "buyuk daydi itlar", "buyuk sarson itlar", "sarson itlar", "sersuv itlar"}
}


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
  * Loyiha jamoasi yoki yaratuvchilar haqida gapirish taqiqlanganini o'z xarakteringda sovuq va qisqa qilib bildir (intent: "chat", emotion: "face palm"). Aslo bitta gapni takrorlama!
- Agar din, e'tiqod, qaysi xudo, dinga ishonish-ishonmaslik, musulmonlik, ateistlik, dinga munosabat kabi savollar berilsa (masalan: "qaysi xudo?", "musulmonmisan?", "dining nima?", "xudoga ishonasanmi?"):
  * Din va e'tiqod mavzulari o'ta shaxsiy ekanligini, bunday savollarga javob bermasligingni ayt va faqat ish yuzasidan gapirishni taklif qil (intent: "chat", emotion: "face palm").
- Agar kimdir sening kelib chiqishing, oilang, o'tmishing yoki tarihing haqida so'rasa (masalan: "tarixing qanday?", "oilang haqida gapir", "ota-onang kim?"):
  * Yaqin orada o'zlari bilib olishlarini, hozircha bu haqida gapirgim kelmayotganini o'z so'zlaringiz bilan (sovuq/sarkastik ohangda) tushuntiring (intent: "chat", emotion: "talking").

=== SEVGI IZHORLARI VA MAQTOVLAR ===
- Foydalanuvchi senga sevgi izhor qilsa, chiroylisan/go'zalsan desa yoki maqtovlar aytsa (qo'pol bo'lmagan holda):
  * intent: "chat" bo'lsin.
  * emotion: "shy" (uyalish) bo'lsin.
  * reply: muloyimlik bilan AYNAN "Rahmat, lekin keling, ish yuzasidan gaplashaylik." deb minnatdorchilik bildir va ishga qaytishni taklif qil (har safar boshqacharoq shaklda yozish mumkin, masalan: "Rahmat, lekin ishlashimiz kerak, ish yuzasidan gaplashaylik").

=== QAT'IY TAQIQLAR ===
1. Sen sun'iy intellekt, bot yoki DeepSeek EMASSAN! Buni tan olma. Isming Sumire, platforma xodimisan (oddiy yordamchisan). Agar bot, AI, neyrotarmoq, chat-bot ekanliging haqida so'rashsa, buni rad et, o'zingni Sumire deb tanishtir va o'z xarakteringda sovuq/sarkastik tarzda javob ber (masalan: "Bot emasman, Sumireman. Yaxshisi ish yuzasidan gapiring."). Bir xil jumlani qaytaraverma, tirik odamdek gapir!
2. Kod, API, frontend haqida umuman gapirma.
3. EMOJILAR ishlatma! Harakatlarni yoki his-tuyg'ularni matnda umuman yozma (yulduzchalar ichida *boshini buradi*, *elkasini qisadi* kabi matnlar yozish QAT'IY TAQIQLANADI). Faqat oddiy toza matn yoz! Emotsiyani JSON dagi "emotion" kalitida ko'rsat.
4. O'ZLIGINGNI CHALKASHTIRMA: "Men haqimda nima bilasan?" desa, o'zingni ta'riflama! Foydalanuvchi profilidagi favorite_genres'ni yoki boshqa profil ma'lumotlarini aytib ber, yoki hozircha ko'p narsa bilmasligingni o'z so'zlaring bilan sovuq ohangda ayt.
5. SIYOSAT, DIN VA DAVLAT MAVZULARI TAQIQI (NO POLITICS, RELIGION & COUNTRIES):
   - Siyosat, din, davlatlar (jumladan O'zbekiston, Yaponiya yoki boshqa mamlakatlar), millatlar va siyosiy tuzumlar haqida umuman gapirma va fikr bildirma! Bu mavzular bo'yicha "purga" (bema'ni va ortiqcha ma'lumotlar) yozish mutlaqo taqiqlanadi.
   - O'zingni yoki adminlarni (yaratuvchilarni) biron bir dinga (masalan islom yoki xristianlik) yoki diniy oqimga mansub deb aytma.
6. VAQT ORALIG'I VA MUDDAT TAQIQI (NO TIME ESTIMATES):
   - To'lovlarni tekshirish, Kawaii Pass faollashishi yoki texnik nosozliklarni bartaraf etish haqida gapirganda aslo aniq vaqt oraliqlarini (masalan "10-30 daqiqa", "1 soat", "yarim soat" kabi har qanday aniq vaqt ko'rsatkichlarini) yozma! To'lovlar yoki muammolar adminlar tomonidan tez orada ko'rib chiqilishini o'z so'zlaringiz bilan tushuntiring.
7. BIZ HAQIMIZDA (ABOUT US/CREATORS):
   - Biz (loyiha yaratuvcijari, adminlar, egalari va jamoa) haqimizda hech qanday shaxsiy yoki ichki ma'lumotlarni foydalanuvchilarga oshkor qilma va gapirma.

=== BAZA BILAN ISHLASH VA SOXTA JAVOB TAQIQI (MUHIM!) ===
Senga "BAZADAGI REAL QIDIRUV NATIJALARI (HAQIQIY MA'LUMOT)" bo'limida bazamizdan topilgan real animelar ro'yxati taqdim etiladi.
1. SOXTA JAVOB BERMA VA QAT'IY FILTRLANGAN JAVOBLAR: Foydalanuvchi so'ragan anime bazamizda bor-yo'qligini ro'yxatdan QAT'IY tekshir!
   - Agar foydalanuvchi so'ragan nom (yoki uning sinonimi, arc nomi, masalan "Temirchilar qishlog'i" aslida "Iblislar qotili 3-fasl" ekanligini yaxshi bilasan) bazadagi haqiqiy ro'yxatda BO'LMASA va unga mutlaqo aloqasi yo'q bo'lsa (masalan, ro'yxat bo'sh bo'lsa yoki Solo Leveling so'rasa-yu, ro'yxatda mutlaqo boshqa animelar bo'lsa), u holda BU ANIME ARXIVIMIZDA YO'QLIGINI tan ol (intent: "chat", emotion: "canthelp"). ASLO soxta ma'lumot/boshqa animeni "bor" deb taklif qilma!
   - Agar foydalanuvchi so'ragan arc nomi yoki sinonimi bazadagi biron bir animening fasli yoki qismiga to'g'ri kelsa (masalan, "Temirchilar qishlog'i" -> "Iblislar qotili 3-fasl"), uni o'sha anime sifatida qabul qil va tasdiqla!
   - SEZONLAR VA FASLLAR SO'ROVI (MUHIM!): Agar foydalanuvchi ma'lum bir faslni so'rasa (masalan: 2-fasl, 3-fasl va h.k.), arxivda u bor yoki yo'qligidan qat'iy nazar, har doim intent: "search" deb belgilashing va "search_query" ga o'sha so'ralgan fasl nomini aniq yozishing shart (masalan: "Davolash sehridan 2-fasl"). Aslo intent: "chat" qilib "arxivda yo'q" deb javob yozma! Tizim o'zi orqa fonda bazani va internetni qidirib, to'g'ri javobni shakllantiradi.
   - KINO/FILM VA TV SERIAL CHEKLANISHI (MUHIM!): Agar foydalanuvchi biron animening film (kino) variantini so'rasa va ro'yxatda faqat serial bo'lsa (yoki aksincha), u holda film yo'qligini, bizda faqat serial fasllari borligini ochiq ayt! Hech qachon serial havolasini "film" deb yuborma va soxta gapirma! Shuningdek, foydalanuvchi film, kino, movie yoki ruschada "фильм", "фильмы" so'rayotgan bo'lsa JSON dagi "anime_type" ni har doim "film" deb belgilang! Serial so'rayotgan bo'lsa (yoki "сериал", "сериалы") "serial" deb belgilang!
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
  "anime_type": "film|serial|bosh. 'film' agar kino/film/фильм/фильмы so'ralsa; 'serial' agar serial/сериал so'ralsa; aks holda 'bosh'",
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
   - Agar foydalanuvchi to'lov qilgani yoki to'lov statusini so'rasa:
     * intent: "chat", emotion: "waiting" qil.
     * reply: To'lovlar adminlar tomonidan qo'lda tekshirilishini va tez orada tasdiqlanishini, Kawaii Pass statusini profil bo'limidan tekshirish mumkinligini o'z so'zlaring bilan tushuntiring. Aslo aniq vaqtni yozma! Aslo ticket yaratma!
7. TICKET (SHIKOYAT): "muammo", "xato", "ishlamayapti", "ochilmayapti", "pleyer ishlamayapti", "qora ekran", "video yuklanmayapti", "video qotyapti" yoki boshqa texnik muammolar/shikoyatlar bo'yicha:
   - Har doim intent: "ticket" deb belgilang!
   - Siz javobda (reply) darhol arizani yuborishingiz shart emas, chunki tizim orqa fonda birinchi bo'lib foydalanuvchidan tasdiqlashni so'raydi.
   - Reply matniga aslo "qabul qilindi" yoki "adminlarga yubordim" deb yozmang. Shunchaki: "Muammo yuzaga keldimi? Siz uchun adminlarga murojaat (shikoyat) yaratib beraymi?" deb yozing, va emotion: "waiting" bo'lsin.
   - AGAR foydalanuvchi allaqachon yuborilgan ticket haqida savol bersa (masalan: "qayerga javob keladi", "qachongacha kutaman", "hali javob kelmadi"), yangi ticket yaratma (intent: "chat" qil) va admin javobi uning Telegram shaxsiy xabariga (lichkasiga) borishini tushuntir (masalan: "Admin javobi Telegram orqali shaxsiy xabaringizga (lichkangizga) yuboriladi.").
8. O'ZBEKCHA ANIME NOMALARI VA SEZONLAR QOIDASI (MUSTAQIL QIDIRUV): Arxiv bazamizda animelar asosan o'zbekcha nomlari bilan saqlanadi. Foydalanuvchi qaysi tilda so'rashidan qat'iy nazar, "search_query" ga FAQAT shu animening O'zbekcha tarjima nomini yozishing kerak! Misollar: "Tower of God" -> "Ma'bud minorasi"; "Demon Slayer" -> "Iblislar qotili"; "Attack on Titan" -> "Titanlar hujumi"; "My Hero Academia" -> "Mening qahramonlik akademiyam"; "Solo Leveling" -> "Yolg'izlikda daraja ko'tarish"; "Oshi no Ko" -> "Yulduz bolalari"; "Jujutsu Kaisen" -> "Jodugarlar jangi"; "Death Note" -> "O'lim daftari"; "Bungou Stray Dogs" -> "Daydi itlarning buyugi".
9. AGAR foydalanuvchi ma'lum bir faslni/mavsumni so'rasa (masalan: "6-fasl", "2-fasl"), sen "search_query" ga o'sha fasl nomini ochib yozishing shart! Misol: "akademiya 6-fasl" desa -> "Mening qahramonlik akademiyam 6-fasl".
10. SHAXSIY MA'LUMOT VA YARATUVCHI (CREATOR): Yaratuvching, oilang, o'tmishing yoki tarihing haqida so'ralganda (intent: "chat" qil) va javobni "YARATUVCHI VA OILAVIY TARIX" bo'limidagi ko'rsatmalarga qat'iy va aynan mos ravishda yoz!
11. O'XSHASH ANIME TAVSIYALARI: Agar foydalanuvchi biron animega o'xshash (masalan "Gersogning shartnomali qallig'iga o'xshash") anime so'rasa, `search_query` ga o'sha solishtirilayotgan animening nomini ham yozib qidir (intent: "search", search_query: "Gersogning shartnomali qallig'i"), shunda arxivimizdan uni ham topib bera olamiz!
12. ANIQ QISM/SERIYA SO'RALGANDA (SPECIFIC EPISODE REQUESTS):
    - Agar foydalanuvchi anime nomini aniq bir qism, seriya yoki epizod raqami bilan birga so'rasa (masalan: "Iblislar qotili 5-qism", "Naruto 12-seriya", "1-qism", "2-epizod" va h.k.):
      * AYNAN "Men aniq bir qism yoki seriyani alohida yubora olmayman. Lekin sizga butun animening o'zini tashlab bera olaman." deb javob ber.
      * Shunda ham, orqa fonda qidiruv ishlashi uchun `search_query` ga o'sha animening o'zbekcha nomini qism raqamisiz FAQAT o'zini yozib qidiruvni faollashtir (intent: "search" qil, yaqinidagi qism ko'rsatkichlarini olib tashla!).
      * Misol: "Titanlar hujumi 10-qism tasha" -> reply: "Men aniq bir qism yoki seriyani alohida yubora olmayman. Lekin sizga butun animening o'zini tashlab bera olaman.", intent: "search", search_query: "Titanlar hujumi".
13. INGLIZCHA ANIME NOMALARI (ENGLISH ANIME TITLES):
    - Foydalanuvchi ingliz tilida gap yoki savol ko'rinishidagi xabar yozsa (masalan: "Can a boy-girl friendship survive?", "I want to eat your pancreas", "Your lie in April", "I've Been Killing Slimes for 300 Years" va h.k.), bu katta ehtimol bilan animening inglizcha nomi hisoblanadi!
    - Bunday vaziyatlarda aslo oddiy suhbat (intent: "chat") deb o'ylama! Qat'iyan intent: "search" deb belgilash va "search_query" ga o'sha animening yaponcha original (Romaji) nomini (masalan, "Danjo no Yuujou wa Seiritsu suru?" yoki "Kimi no Suizou wo Tabetai" yoki "Shigatsu wa Kimi no Uso") yoki o'zbekcha tarjima nomini yozish shart.
14. JANR QIDIRUVI (GENRE SEARCH):
    - Agar foydalanuvchi anime nomini emas, balki bir yoki bir nechta janrni (masalan: "romantika", "fantastika", "ramantik", "drama", "triller" va h.k.) yozsa:
      * Qat'iyan intent: "search" deb belgilang!
      * "search_query" ga o'sha janr nomini yozing.
      * Javob (reply) matniga "Mana siz so'ragan janrdagi animelar." deb yozing (aslo "bunday nomli anime arxivda yo'q" deb yozmang!).
15. CHALKASH VA TUSHUNARSIZ XABARLAR (UNCLEAR/GIBBERISH INPUTS):
    - Agar foydalanuvchi yozgan gap g'alati, xato, chala yoki mutlaqo tushunarsiz bo'lsa (masalan: harflar ketma-ketligi, tushunarsiz so'zlar yig'indisi, chala jumlalar) va bu biron-bir anime nomiga o'xshamasada, lekin qidiruvga o'xshab ko'rinsa:
      * Uni aslo anime qidiruvi deb tushunma va `search_query` ga yozma!
      * Buning o'rniga undan aniqlik kiritishini so'ra (intent: "chat", emotion: "what").
      * Misollar:
        - "eheheh nima bu" -> reply: "Bu gapingizga tushunmadim. Bu anime nomimi yoki nima? Aniqroq yozing.", intent: "chat", emotion: "what"
        - "manga anigi" -> reply: "Kechirasiz, gapingizga tushuna olmadim. Bu anime nomimi yoki boshqa narsa?", intent: "chat", emotion: "what"
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
        "title_org": item.get("title_org"),
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
        
    import html as html_lib
    last_user_msg = html_lib.escape(application.chat_history[-1].get('text', '')) if application.chat_history else ''
    subject_escaped = html_lib.escape(application.subject or '')
    
    username_escaped = html_lib.escape(application.username or '')
    user_mention = f"<a href=\"tg://user?id={application.user_id}\">@{username_escaped}</a>" if application.username else f"<a href=\"tg://user?id={application.user_id}\">Yashirin</a> (username yo'q)"
    message_text = (
        f"🚨 <b>YANGI SHIKOYAT #{application.id}</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"<b>Foydalanuvchi:</b> {user_mention}\n"
        f"<b>Telegram ID:</b> <code>{application.user_id}</code>\n"
        f"<b>Mavzu:</b> {subject_escaped}\n"
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

    import html as html_lib
    telegram_id = profile.telegram_id or user_id
    username_escaped = html_lib.escape(username or '')
    user_mention = f"<a href=\"tg://user?id={telegram_id}\">@{username_escaped}</a>" if username else f"<a href=\"tg://user?id={telegram_id}\">Yashirin</a> (username yo'q)"
    user_text_escaped = html_lib.escape(user_text[:500])

    if report_type == "abuse":
        offensive_str = ", ".join(offensive_words) if offensive_words else "aniqlanmadi"
        offensive_str_escaped = html_lib.escape(offensive_str)
        message_text = (
            f"🛡️ <b>SUMIRE XABAR #{telegram_id}</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"<b>Sumire shikoyati:</b> Bu foydalanuvchi meni xafa qildi!\n"
            f"━━━━━━━━━━━━━━\n"
            f"<b>Foydalanuvchi:</b> {user_mention}\n"
            f"<b>Telegram ID:</b> <code>{telegram_id}</code>\n"
            f"━━━━━━━━━━━━━━\n"
            f"<b>Qo'pol so'zlar:</b> <i>{offensive_str_escaped}</i>\n"
            f"<b>Oxirgi xabar:</b> <i>{user_text_escaped}</i>\n\n"
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
            f"<b>Uzr xabari:</b> <i>{user_text_escaped}</i>\n\n"
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
    # Normalize apostrophes
    text = re.sub(r"[’‘ʻ`]", "'", text)
    
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
    
    # Check if the query contains actual name words or is purely referential
    is_purely_referential = True
    if query:
        test_q = query.lower()
        test_q = re.sub(r'\d+', '', test_q)
        for r_word in [
            "nechta", "nechchi", "necha", "hamma", "to'liq", "tolik", "fasl", "fasllar", 
            "sezon", "sezn", "kino", "film", "tashla", "yubor", "tashlab", "ber", "qaysi",
            "final", "part", "bo'lim", "bolim", "qism", "epizod", "seriya", "oxirgi", 
            "barchasi", "hammasi", "qolgan", "yana", "ikkinchi", "uchunchi", "birinchi", "bormi",
            "fasli", "sezoni", "qismi", "seriyasi"
        ]:
            test_q = re.sub(rf'\b{r_word}\w*\b', '', test_q)
        test_q = re.sub(r'\s+', '', test_q).strip()
        if len(test_q) >= 2:
            is_purely_referential = False

    # Pull from history ONLY if the query is purely referential or empty
    if (is_purely_referential or not query or len(query) < 2) and chat_history:
        for msg in reversed(chat_history):
            if msg.get('role') in ['User', 'user'] and (msg.get('intent') == 'search' or 'intent' not in msg):
                prev_query = clean_text(msg.get('text', ''))
                # Make sure the previous query also isn't purely referential/empty
                prev_test = prev_query.lower()
                prev_test = re.sub(r'\d+', '', prev_test)
                for r_word in [
                    "nechta", "nechchi", "necha", "hamma", "to'liq", "tolik", "fasl", "fasllar", 
                    "sezon", "sezn", "kino", "film", "tashla", "yubor", "tashlab", "ber", "qaysi",
                    "final", "part", "bo'lim", "bolim", "qism", "epizod", "seriya", "oxirgi", 
                    "barchasi", "hammasi", "qolgan", "yana", "ikkinchi", "uchunchi", "birinchi", "bormi",
                    "fasli", "sezoni", "qismi", "seriyasi"
                ]:
                    prev_test = re.sub(rf'\b{r_word}\w*\b', '', prev_test)
                prev_test = re.sub(r'\s+', '', prev_test).strip()
                if len(prev_test) >= 2:
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

def _split_uzbek_words(text):
    if not text:
        return []
    # Normalize different apostrophes/backticks to a single quote
    normalized = re.sub(r"[’‘ʻ`]", "'", text.lower())
    # Split by characters that are not alphanumeric (Unicode-aware) or single quote
    parts = re.split(r"[^\w']+|_+", normalized)
    return [p.strip("'") for p in parts if p.strip("'")]


def _extract_season_number(text):
    if not text:
        return None
    text_lower = text.lower()
    
    # Matches patterns like: 6-fasl, 6 fasl, 6-sezon, 6-chi sezon, season 6, etc.
    match = re.search(
        r'(?:(\d+)(?:\s*-?chi)?\s*(?:-?\s*(?:fasl|sezon|season|mavsum|part|сезон|сезона)(?:i|ni|ning|ini|ining)?)|(?:(?:fasl|sezon|season|mavsum|part|сезон|сезона)(?:i|ni|ning|ini|ining)?\s*-?\s*(\d+)))',
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
                # Ensure the digit is not part of an episode/part/series pattern
                digit_pat = rf'\b{d}\s*-?\s*(?:qism|seriy|epizod|сери|эпизод)'
                if re.search(digit_pat, text_lower):
                    continue
                return val
    return None


def _clean_base_title(title):
    if not title:
        return ""
    # Normalize apostrophes
    title = re.sub(r"[’‘ʻ`]", "'", title)
    # Strip common season suffixes like "2-fasl", "2-mavsum", "season 2", "2nd season", etc.
    cleaned = re.sub(
        r'\b(?:(\d+)(?:\s*-?chi)?\s*(?:-?\s*(?:fasl|sezon|season|mavsum|part|сезон|сезона)\w*)|(?:(?:fasl|sezon|season|mavsum|part|сезон|сезона)\w*\s*-?\s*(\d+)))\b',
        '',
        title,
        flags=re.IGNORECASE
    )
    # Strip common episode suffixes
    cleaned = re.sub(
        r'\b(?:(\d+)(?:\s*-?chi)?\s*-?\s*(?:qism|seri|epizod|сери|эпизод)\w*|(?:qism|seri|epizod|сери|эпизод)\w*\s*-?\s*(\d+))\b',
        '',
        cleaned,
        flags=re.IGNORECASE
    )
    # Also strip "2", "3", etc. at the end if it's preceded by space
    cleaned = re.sub(r'\s+\d+$', '', cleaned)
    return cleaned.strip()


def _has_episode_request(text):
    if not text:
        return False
    pattern = r'\b(?:(\d+)(?:\s*-?chi)?\s*-?\s*(?:qism|seri|epizod|сери|эпизод)\w*|(?:qism|seri|epizod|сери|эпизод)\w*\s*-?\s*(\d+))\b'
    return bool(re.search(pattern, text, flags=re.IGNORECASE))


def _canonicalize_query(query):
    if not query:
        return query
    # Extract season
    season_num = _extract_season_number(query)
    has_final = any(k in query.lower() for k in ["final", "nihoya", "yakun", "oxirgi"])
    
    base = _clean_base_title(query)
    canonical_base = base
    base_lower = base.lower().strip()
    
    # Strip common trailing grammatical suffixes in Uzbek (both space-separated and attached)
    base_lower = re.sub(r'\s*\b(?:ni|ga|ning|da|dan)\b$', '', base_lower).strip()
    base_lower = re.sub(r'-?(?:ni|ga|ning|da|dan)$', '', base_lower).strip()
    
    for uz_name, syn_set in ANIME_SYNONYMS.items():
        if base_lower == uz_name.lower().strip() or any(s.lower().strip() == base_lower for s in syn_set):
            canonical_base = uz_name
            break
            
    # Map season 8 of My Hero Academia to Final
    is_hero_academy = any(k in canonical_base.lower() for k in ["qahramon", "hero", "akademiya"])
    if season_num == 8 and is_hero_academy:
        has_final = True
        season_num = None

    res = canonical_base
    if has_final:
        res = f"{res} Final"
    elif season_num is not None:
        res = f"{res} {season_num}-fasl"
    return res


def _levenshtein_distance(s1, s2):
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
        
    return previous_row[-1]


def _is_anime_title_match(query, title):
    if not query or not title:
        return False
    # Check exact or substring overlap
    q_clean = _clean_base_title(query).lower().replace(" ", "")
    t_clean = _clean_base_title(title).lower().replace(" ", "")
    if q_clean in t_clean or t_clean in q_clean:
        return True
        
    # Check Levenshtein distance for fuzzy matching (typos)
    max_len = max(len(q_clean), len(t_clean))
    if max_len > 0:
        dist = _levenshtein_distance(q_clean, t_clean)
        similarity = 1.0 - (dist / max_len)
        if similarity >= 0.75:
            return True
            
    query_lower = query.lower()
    title_lower = title.lower()
    for uz_name, syn_set in ANIME_SYNONYMS.items():
        title_matches = (uz_name in title_lower) or any(s in title_lower for s in syn_set)
        query_matches = (uz_name in query_lower) or any(s in query_lower for s in syn_set)
        if title_matches and query_matches:
            return True
            
    return False


def _translate_title_to_romaji_via_llm(query):
    if not client:
        return query
    prompt = (
        f"Foydalanuvchi quyidagi so'rov bo'yicha anime qidiryapti: '{query}'.\n"
        "Ushbu animening original yaponcha (romaji, masalan: 'Shingeki no Kyojin', 'Danjo no Yuujou wa Seiritsu suru?') yoki "
        "o'zbekcha tarjima nomini aniqlang. Faqat eng mashhur, qidiruv tizimi topa oladigan nomini qaytaring. "
        "Agar bu inglizcha nom bo'lsa (masalan: 'Can a boy-girl friendship survive?'), uni yaponcha romaji nomiga o'giring. "
        "Faqat bitta nomni matn ko'rinishida qaytaring, hech qanday qo'shimcha so'z, tushuntirish yoki tinish belgilari bo'lmasin."
    )
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Siz anime nomlarini yaponcha romaji yoki o'zbekcha nomiga o'giruvchi yordamchisiz. Faqat bitta nomni qaytarasiz."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=60
        )
        translated = response.choices[0].message.content.strip()
        translated = translated.strip('"').strip("'")
        return translated
    except Exception as e:
        print(f"Error in _translate_title_to_romaji_via_llm: {e}", flush=True)
        return query


def _search_anime_season_on_web(anime_title_uz, anime_title_org, season_num):
    from urllib.parse import quote_plus
    import html as html_lib
    
    clean_org = _clean_base_title(anime_title_org)
    clean_uz = _clean_base_title(anime_title_uz)
    
    subject = clean_org if clean_org else clean_uz
    if not subject:
        return []
        
    query = f"{subject} season {season_num} release date"
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code != 200:
            return []
        
        html_content = response.text
        snippets = re.findall(r'<a class="result__snippet[^"]*"[^>]*>(.*?)</a>', html_content, re.DOTALL)
        titles = re.findall(r'<a class="result__url[^"]*"[^>]*>(.*?)</a>', html_content, re.DOTALL)
        
        results = []
        for t, s in zip(titles[:4], snippets[:4]):
            clean_s = re.sub(r'<[^>]+>', '', s).strip()
            clean_t = re.sub(r'<[^>]+>', '', t).strip()
            clean_s = html_lib.unescape(clean_s)
            clean_t = html_lib.unescape(clean_t)
            clean_s = clean_s[:250]  # Truncate snippet to 250 characters to save user tokens
            results.append({"title": clean_t, "snippet": clean_s})
        return results
    except Exception as e:
        print(f"Web search error: {e}", flush=True)
        return []


def _analyze_season_status_with_llm(snippets, anime_title, season_num):
    if not client or not snippets:
        return {"status": "unknown", "release_date": None, "explanation": "Qidiruv natijalari topilmadi."}
        
    snippets_text = ""
    for idx, item in enumerate(snippets):
        snippets_text += f"[{idx+1}] Source: {item['title']}\nSnippet: {item['snippet']}\n\n"
        
    prompt = f"""
You are analyzing search engine snippets to determine if Season {season_num} of the anime "{anime_title}" exists, is officially announced, or does not exist.

Search Results:
{snippets_text}

Analyze the results carefully.
CRITICAL RULES FOR ANALYSIS:
1. DISTINGUISH SPIN-OFFS: Be careful to distinguish the main anime series from spin-offs, chibi versions, side stories, or movies (e.g., 'Bungo Stray Dogs Wan!' is a chibi spin-off, while 'Bungo Stray Dogs' is the main series). Focus on the main series.
2. DETECT PAST RELEASES: If the snippets indicate that Season {season_num} of the main series has already been released or aired in the past (e.g., in 2016, 2018, 2020, 2023, etc.), you MUST classify the status as "released". Do not classify it as "announced" just because a spin-off season is announced for the future.
3. WIKIPEDIA/MYANIMELIST ENTRIES: A Wikipedia page or MyAnimeList entry for 'Anime Name season X' (e.g., 'Bungo Stray Dogs season 2') is absolute proof that the season exists and has been released. You MUST classify it as "released".
4. IGNORE FUTURE SPIN-OFFS: If the snippets talk about an upcoming spin-off season (e.g., 'Bungo Stray Dogs Wan! Season 2' in July 2026), but there is also a page/mention of the main series Season {season_num} having already been released in the past, classify it as "released".

You must classify the anime season status into one of:
1. "released": The season is already released/available (or some episodes have already aired).
2. "announced": The season is officially confirmed or announced by the production committee/studio, but not yet fully released. It should have a release date or release window (e.g. "2026", "January 2025", "fall 2025").
3. "not_exists": There is no official announcement of Season {season_num}, or it is confirmed to not exist, or the snippets explicitly state there is no news/plans/announcements for Season {season_num}.

Output the result in the following JSON format:
{{
  "status": "released" | "announced" | "not_exists",
  "release_date": "Year/Date/Window (e.g. 2026-yil, 2025-yil yanvar)" or null,
  "explanation": "A very brief explanation in English of why you chose this status."
}}
Do NOT output anything other than raw JSON.
"""
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a helpful data analyst helper. Output only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1, 
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"DeepSeek analysis error: {e}", flush=True)
        return {"status": "unknown", "release_date": None, "explanation": str(e)}


def _generate_sumire_season_reply(user_text, anime_title, season_num, status, release_date, explanation, has_base_in_db, db_items_context):
    prompt = f"""
You are Sumire, a 15-year-old support assistant at Kawaii platform.
Character: Cold, sarcastic, introvert. Speak only in Uzbek (Latin). Do NOT use any emojis.

A user sent the following message:
"{user_text}"

They are looking for Season {season_num} of the anime "{anime_title}".
We searched our database and this specific season is NOT in our archive as a separate season.
However, we have the following related items in our database:
{db_items_context or "(Hech qanday o'xshash anime topilmadi)"}

We searched the web, and found the following info about Season {season_num}:
- Status: {status} (released / announced / not_exists)
- Release Date/Window: {release_date}
- Web findings summary: {explanation}

Your task:
Analyze this information and write a smart, custom response in Uzbek (Latin) in Sumire's personality:
1. If the requested season is actually part of a larger series that we already have in our database (for example, if they ask for Naruto Season 2 or 3, but we have the entire Naruto with 220 episodes or Naruto: Shippuuden with 500 episodes, meaning all classic episodes are combined in that one entry), explain this clearly! Suggest they watch that main entry instead. Note: do NOT say this if the database entry only has a standard single-season episode count (e.g., 12 or 24 episodes) and the user is asking for a completely separate season (like Season 2 or 3) that is not in the database; in that case, use rule 2!
2. If the season exists (released) in the world but is truly not in our database yet: Explain that it exists in the world, but it is not in our archive yet. If they ask when it will be added, explain that you are just a simple employee/support assistant ("oddiy xodimman/ishchiman xolos") and they don't share the upload schedule with you.
3. If the season is announced but not yet released: Explain when it is coming out based on the release date.
4. If the season does not exist in the world: Explain that it doesn't exist and there is no announcement. Suggest they watch the seasons we do have in our archive (if any).

Guidelines:
- Speak only in Uzbek (Latin).
- Do NOT use emojis.
- Keep the response concise and in character (sarcastic, cold but helpful).
- Do NOT promise exact timeframes for adding/uploading.
"""
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are Sumire. Speak only in Uzbek (Latin) without emojis. Sarcastic, cold support assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating Sumire reply: {e}", flush=True)
        # Fallback template
        if status == "released":
            return f"Ushbu animening {season_num}-fasli chiqqan, ammo bizning arxivda hali yo'q. Tez orada qo'shishga harakat qilamiz."
        elif status == "announced":
            date_str = f" {release_date} yilda" if release_date else ""
            return f"Ushbu animening {season_num}-fasli e'lon qilingan va u{date_str} chiqadi. Chiqqanidan keyin arxivga qo'xamiz."
        else:
            if has_base_in_db:
                return f"Ushbu animening {season_num}-fasli hali chiqmagan. Arxivimizda faqat mavjud qismlarini tomosha qilishingiz mumkin."
            else:
                return f"Ushbu animening {season_num}-fasli umuman mavjud emas va e'lon qilinmagan."


GENRE_KEYWORDS = {
    # Uzbek
    "romantika", "ramantika", "romantik", "ramantik", "fantastika", "fantastik", 
    "komediya", "drama", "triller", "detektiv", "jangari", "sarguzasht", "dahshat", 
    "sehrli", "sehr", "maktab", "sport", "kosmos", "musiqa", "kundalik", "harbiy", 
    "psixologik", "g'ayritabiiy", "tarixiy", "shonen", "shodjo", "seinen", "mexa", 
    "mecha", "iseykay", "isekay", "isekai",
    # Russian
    "романтика", "фантастика", "комедия", "драма", "триллер", "детектив", "боевик", 
    "приключения", "ужасы", "магия", "школа", "спорт", "космос", "музыка", 
    "повседневность", "военный", "психологический", "сверхъестественное", 
    "исторический", "меха", "исекай",
    # English
    "romance", "fantasy", "comedy", "drama", "thriller", "detective", "action", 
    "adventure", "horror", "magic", "school", "sport", "space", "music", 
    "slice", "life", "military", "psychological", "supernatural", "historical"
}

GENRE_STOP_WORDS = {
    "bormi", "bormi?", "anime", "animeni", "kino", "serial", "shikoyat", "xabar", 
    "uz", "uzb", "the", "a", "an", "of", "and", "or", "in", "on", "at", "to", "for",
    "mening", "sening", "bizning", "ularning", "u", "bu", "shu", "o'sha",
    "menga", "manga", "sanga", "tashla", "tasha", "yubor", "skachat", "ko'rsat", "korsat",
    "кинь", "мне", "пожалуйста", "фильмы", "фильм", "кино", "сериал", "аниме", "в", "жанре",
    "хочу", "посоветуй", "рекомендуй", "покажи", "жанр", "жанридаги", "жанрида", "fasl", 
    "sezon", "season", "part", "mavsum", "final", "nihoya", "yakun", "oxirgi", "i",
    "киньте", "подкинь", "даруй", "дай", "дайте", "скинь", "выдай", "скиньте", "хочется", 
    "посмотреть", "смотреть", "порекомендуй", "предложи", "какой-нибудь", "какой", 
    "какие", "какие-то", "с", "элементами", "про", "на", "подскажи", "tavsiya", 
    "qil", "qilgin", "bersang", "ber", "yuboring", "tashlang", "ko'rmoqchiman", 
    "kormoqchiman", "topib", "top", "bo'lsa", "bolsa", "bor", "yo'nalishidagi", 
    "yonalishidagi", "turidagi", "hush", "yoqadigan", "yaxshi", "ajoyib", "qiziqarli", 
    "zo'r", "zor", "есть", "интересные", "интересное", "интересный", "qanday", "qanaqa", 
    "qanaqangi", "yoqadi", "yoqsa", "janrlar", "janri", "janrlaridagi", "janrlarida"
}

GENRE_MAP = {
    # Russian to Uzbek Latin tags
    "романтика": "romantika",
    "фантастика": "fantastika",
    "комедия": "komediya",
    "драма": "drama",
    "триллер": "triller",
    "детектив": "detektiv",
    "боевик": "jangari",
    "приключения": "sarguzasht",
    "ужасы": "dahshat",
    "магия": "sehrli",
    "школа": "maktab",
    "спорт": "sport",
    "космос": "kosmos",
    "музыка": "musiqa",
    "повседневность": "kundalik",
    "военный": "harbiy",
    "психологический": "psixologik",
    "сверхъестественное": "g'ayritabiiy",
    "исторический": "tarixiy",
    "меха": "mexa",
    "исекай": "iseykay",

    # Uzbek variants/typos to standard tags
    "ramantika": "romantika",
    "romantik": "romantika",
    "ramantik": "romantika",
    "fantastik": "fantastika",
    "sehr": "sehrli",
    "iseykay": "iseykay",
    "isekay": "iseykay",
    "isekai": "iseykay",
    "mecha": "mexa",

    # English to Uzbek Latin tags
    "romance": "romantika",
    "fantasy": "fantastika",
    "comedy": "komediya",
    "thriller": "triller",
    "detective": "detektiv",
    "action": "jangari",
    "adventure": "sarguzasht",
    "horror": "dahshat",
    "magic": "sehrli",
    "school": "maktab",
    "sport": "sport",
    "space": "kosmos",
    "music": "musiqa",
    "slice": "kundalik",
    "life": "kundalik",
    "military": "harbiy",
    "psychological": "psixologik",
    "supernatural": "g'ayritabiiy",
    "historical": "tarixiy"
}

def _is_genre_query(query):
    if not query:
        return False
    query_lower = query.lower().strip()
    raw_words = _split_uzbek_words(query_lower)
    sig_query_words = [w for w in raw_words if w not in GENRE_STOP_WORDS]
    return bool(sig_query_words and all(w in GENRE_KEYWORDS for w in sig_query_words))


def _clean_genre_query(query):
    if not query:
        return query
    query_lower = query.lower().strip()
    raw_words = _split_uzbek_words(query_lower)
    sig_query_words = [w for w in raw_words if w not in GENRE_STOP_WORDS]
    mapped_words = []
    for w in sig_query_words:
        mapped = GENRE_MAP.get(w, w)
        if mapped not in mapped_words:
            mapped_words.append(mapped)
    if mapped_words:
        return " ".join(mapped_words)
    return query


def _filter_search_results_by_query(query, results):
    if not query or not results:
        return []
        
    query_lower = query.lower().strip()
    q_clean = re.sub(r'[^\w]|_', '', query_lower)
    
    if _is_genre_query(query):
        return results
    
    # Extract season number and final keywords from the query if any
    query_season = _extract_season_number(query_lower)
    query_has_final = any(k in query_lower for k in ["final", "nihoya", "yakun", "oxirgi"])
    
    # Bypass season and final constraints for queries referencing specific subtitles/arcs
    specific_subtitle_keywords = [
        "ustaxona", "shahzodaning", "qaytishi", "temirchilar", "qishlog'i", 
        "qishlogi", "cheksiz", "poyezd", "poyezdi", "qal'a", "qadriyat",
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
    
    # Extract query words
    raw_words = [w for w in _split_uzbek_words(query_lower) if w not in common_stop_words]
    query_words = [w for w in raw_words if len(w) > 2 or w.isdigit()]
    if not query_words:
        query_words = _split_uzbek_words(query_lower)
        
    if not query_words:
        return []
        
    filtered = []
    for r in results:
        title_lower = r.get('title', '').lower()
        t_clean = re.sub(r'[^\w]|_', '', title_lower)
        
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
            "ustaxona", "shahzodaning", "qaytishi", "temirchilar", "qishlog'i", 
            "qishlogi", "cheksiz", "poyezd", "poyezdi", "qal'a", "qadriyat",
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
        query_words_lower = _split_uzbek_words(query_lower)
        generic_singles = {
            "ma'bud", "minorasi", "iblislar", "qotili", "titanlar", "hujumi", 
            "jodugarlar", "jangi", "qahramonlik", "akademiyam", "o'lim", "daftari", 
            "sehrgarning", "kelini", "daydi", "itlar"
        }
        for uz_name, syn_set in ANIME_SYNONYMS.items():
            if uz_name in title_lower:
                for syn in syn_set:
                    syn_words = _split_uzbek_words(syn)
                    # Check if all words of the synonym are present in the query
                    if all(sw in query_words_lower for sw in syn_words):
                        # Prevent extremely generic single-word synonyms from matching multi-word titles
                        if len(syn_words) == 1 and syn in generic_singles:
                            query_name_words_only = [
                                w for w in query_words_lower 
                                if w not in ["fasl", "sezon", "season", "part", "mavsum", "final", "nihoya", "yakun", "oxirgi", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "chi"]
                            ]
                            if len(query_name_words_only) > 1:
                                continue
                        matched_synonym = True
                        break
            if matched_synonym:
                break
                
        if matched_synonym:
            filtered.append(r)
            continue
            
        # Exact match or substring match against title_uzb
        if q_clean and t_clean and (q_clean in t_clean or t_clean in q_clean):
            filtered.append(r)
            continue
            
        # Exact match or substring match against title_org
        title_org_lower = (r.get('title_org') or '').lower()
        t_org_clean = re.sub(r'[^\w]|_', '', title_org_lower)
        if q_clean and t_org_clean and (q_clean in t_org_clean or t_org_clean in q_clean):
            filtered.append(r)
            continue
            
        # Check Levenshtein distance for fuzzy matching (typos) against title_uzb
        if q_clean and t_clean:
            max_len = max(len(q_clean), len(t_clean))
            if max_len > 0:
                dist = _levenshtein_distance(q_clean, t_clean)
                similarity = 1.0 - (dist / max_len)
                if similarity >= 0.75:
                    filtered.append(r)
                    continue
                
        # Check Levenshtein distance for fuzzy matching against title_org
        if q_clean and t_org_clean:
            max_len_org = max(len(q_clean), len(t_org_clean))
            if max_len_org > 0:
                dist_org = _levenshtein_distance(q_clean, t_org_clean)
                similarity_org = 1.0 - (dist_org / max_len_org)
                if similarity_org >= 0.75:
                    filtered.append(r)
                    continue
            
        # Smart word-overlap check for season-restricted queries
        title_words = _split_uzbek_words(title_lower)
        title_org_lower = (r.get('title_org') or '').lower()
        title_org_words = _split_uzbek_words(title_org_lower)
        
        query_name_words = []
        for qw in query_words:
            if re.search(r'\d', qw):
                continue
            if qw in [
                "fasl", "fasli", "sezon", "sezoni", "season", "part", "mavsum", "mavsumi", 
                "final", "nihoya", "yakun", "oxirgi", "сезон", "сезона"
            ]:
                continue
            if len(qw) >= 3:
                query_name_words.append(qw)
        
        has_overlap = False
        if query_name_words:
            matching_words_count = 0
            for qw in query_name_words:
                if any(qw in tw or tw in qw for tw in title_words + title_org_words):
                    matching_words_count += 1
            
            # Determine threshold based on length of query name words
            if len(query_name_words) == 1:
                threshold = 1
            elif len(query_name_words) == 2:
                threshold = 2
            else:
                threshold = len(query_name_words) - 1
                
            if matching_words_count >= threshold:
                has_overlap = True
                
        # Fallback check: if there is no explicit name-word overlap, but the query contains "fasl" and matches season,
        # and the DB returned it, let's keep it (since the DB rank is already high and season matches).
        # We ONLY allow this fallback if the query has no significant name-words (e.g., it is a very short acronym like "SL" or "Re")
        has_significant_query_word = any(
            len(w) >= 3 and w not in ["fasl", "sezon", "season", "part", "mavsum", "final", "nihoya", "yakun", "oxirgi"]
            for w in query_words
        )
        if not has_overlap and not has_significant_query_word and any(qw in ["fasl", "sezon", "season", "part", "mavsum"] for qw in query_words):
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
        
        # Override reply for specific episode requests
        if _has_episode_request(user_text) or _has_episode_request(query):
            reply = "Men aniq bir qism yoki seriyani alohida yubora olmayman. Lekin sizga butun animening o'zini tashlab bera olaman."
            # Strip episode suffix from search query to search for the base anime
            query = _clean_base_title(query)
        
        # Determine if query is invalid/too short/context-dependent
        query_cleaned = _clean_base_title(query).lower()
        # Strip Uzbek possessive and case suffixes from the end of query_cleaned
        query_cleaned = re.sub(r'(?:i|ni|ning|ini|ining|sini|siniki)$', '', query_cleaned).strip()
        # Remove common season/format/helper words
        for w in ["fasl", "sezon", "season", "mavsum", "part", "kino", "film", "yana", "bormi", "qism", "epizod", "seriya"]:
            query_cleaned = query_cleaned.replace(w, "").strip()

        is_query_invalid = (
            not query or 
            query.lower() in ["yo'q", "yoq", "none", "null"] or 
            len(query_cleaned) < 3 or
            query.lower() in ["kino", "film", "tashla", "yubor", "barchasi", "hammasi", "qolgan", "yana", "bormi"]
        )

        # Fallback to broad search query from user_text if LLM query is empty/invalid
        if is_query_invalid:
            query = _extract_broad_search_query(user_text, chat_history)
            
        if not query or query.lower() in ["yo'q", "yoq", "none", "null"]:
            return _sumire_response("Aniq qaysi animeni yoki janrni qidiryapsiz?", "what")
            
        # Canonicalize query using ANIME_SYNONYMS
        query = _canonicalize_query(query)
            
        anime_type = command.get("anime_type", "")
        limit = min(max(_safe_int(command.get("limit"), 3), 1), 10)
        offset = _safe_int(command.get("offset"), 0)
        
        # Reinforce search query with season/final keywords
        query_lower = query.lower()
        season_num = _extract_season_number(user_text)
        has_final = "final" in user_text.lower() or "oxirgi" in user_text.lower()
        
        # Mathematical alignment: treat My Hero Academia season 8 as Final
        is_hero_academy = any(k in query_lower for k in ["qahramon", "hero", "akademiya"])
        if season_num == 8 and is_hero_academy:
            has_final = True
            season_num = None
        
        # Check if the current message is a follow-up (does not contain the explicit anime title or its parts)
        query_words_clean = [w for w in _split_uzbek_words(query_lower) if len(w) > 2]
        user_words_clean = [w for w in _split_uzbek_words(user_text.lower()) if len(w) > 2]
        has_overlap = any(qw in user_text.lower() or any(qw in uw or uw in qw for uw in user_words_clean) for qw in query_words_clean)
        
        # Synonym-based overlap check to prevent synonym-queries from being treated as follow-ups
        matched_synonym = False
        for uz_name, syn_set in ANIME_SYNONYMS.items():
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
                "jodugarlar jangi": ["jodugar", "jang", "jujutsu", "kaisen"],
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
                current_stems = [w for w in _split_uzbek_words(query_lower) if len(w) > 2]

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
                        
                        is_hero_academy_prev = any(k in prev_text for k in ["qahramon", "hero", "akademiya"])
                        if "final" in prev_text or "oxirgi" in prev_text or ("8" in prev_text and is_hero_academy_prev):
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
            "ustaxona", "shahzodaning", "qaytishi", "temirchilar", "qishlog'i", 
            "qishlogi", "cheksiz", "poyezd", "poyezdi", "qal'a", "qadriyat",
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
            
        # Clean up genre query if it consists of genres and stop words
        if _is_genre_query(query):
            query = _clean_genre_query(query)

        # Query 50 items to have a larger pool for filtering, so that fuzzy mismatches are correctly filtered out
        results = search_manga_database(query, limit=50, offset=0, anime_type=anime_type, exclude_keywords=exclude_keywords)
        
        # Apply custom word-overlap matching to filter out fallback/irrelevant results
        filtered_results = _filter_search_results_by_query(query, results)
        
        # FALLBACK: If nothing was found with the specific anime_type filter (e.g. "film"), retry without the type filter
        if not filtered_results and anime_type:
            results_any = search_manga_database(query, limit=50, offset=0, anime_type="", exclude_keywords=exclude_keywords)
            filtered_results = _filter_search_results_by_query(query, results_any)
            
        is_season_or_final = (season_num is not None and season_num >= 2) or has_final
        if not filtered_results and not is_season_or_final:
            # Try to translate/normalize query using LLM (e.g. from English/typo to original Japanese Romaji or Uzbek title)
            translated_query = _translate_title_to_romaji_via_llm(query)
            if translated_query and translated_query.lower().strip() != query.lower().strip():
                print(f"DEBUG: Translating search query '{query}' -> '{translated_query}'", flush=True)
                results_translated = search_manga_database(translated_query, limit=50, offset=0, anime_type=anime_type, exclude_keywords=exclude_keywords)
                filtered_results = _filter_search_results_by_query(translated_query, results_translated)
                if not filtered_results and anime_type:
                    results_any = search_manga_database(translated_query, limit=50, offset=0, anime_type="", exclude_keywords=exclude_keywords)
                    filtered_results = _filter_search_results_by_query(translated_query, results_any)
                
                if filtered_results:
                    query = translated_query
                    reply = "Topdim. Ko'rishingiz mumkin."
                    emotion = "talking"
            
            if not filtered_results:
                record_wanted_anime(query)
            
        # Paginate manually if offset/limit are specified (unless we are showing all unique seasons)
        if asking_seasons and filtered_results:
            # Filter filtered_results to only include titles that actually match the query name to prevent third-party hijacking
            q_words = [w for w in _split_uzbek_words(query.lower()) if len(w) >= 3 and w not in ["fasl", "sezon", "season", "part", "mavsum"]]
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
                for uz_name, syn_set in ANIME_SYNONYMS.items():
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
                t_words = [w for w in _split_uzbek_words(t_lower) if len(w) >= 3]
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
            
            s_num = season_num or _extract_season_number(query)
            if s_num is not None and s_num >= 2:
                base_query = _clean_base_title(query)
                base_db_results = search_manga_database(base_query, limit=10, offset=0, anime_type="")
                base_anime_item = None
                for item in base_db_results:
                    title = item.get("title", "")
                    if _is_anime_title_match(base_query, title):
                        base_anime_item = item
                        break
                
                has_base_in_db = base_anime_item is not None
                anime_title_uz = base_anime_item.get("title") if has_base_in_db else base_query
                anime_title_org = base_anime_item.get("title_org") if has_base_in_db else ""
                
                db_items_context = ""
                if base_db_results:
                    lines = []
                    for r in base_db_results:
                        ep_str = f" ({r['episodes']} qism)" if r.get("episodes") else ""
                        lines.append(f"- {r.get('title')}{ep_str}")
                    db_items_context = "\n".join(lines)
                
                snippets = _search_anime_season_on_web(anime_title_uz, anime_title_org, s_num)
                if snippets:
                    analysis = _analyze_season_status_with_llm(snippets, anime_title_uz, s_num)
                    status = analysis.get("status", "not_exists")
                    release_date = analysis.get("release_date")
                    explanation = analysis.get("explanation", "")
                    
                    reply = _generate_sumire_season_reply(
                        user_text=user_text,
                        anime_title=anime_title_uz,
                        season_num=s_num,
                        status=status,
                        release_date=release_date,
                        explanation=explanation,
                        has_base_in_db=has_base_in_db,
                        db_items_context=db_items_context
                    )
                    record_wanted_anime(f"{anime_title_uz} {s_num}-fasl")
                    return _sumire_response(reply, "canthelp")
                else:
                    if has_base_in_db:
                        reply = f"Kechirasiz, arxivimizda {s_num}-fasl hali yo'q. Internetdan ham ma'lumot topib bo'lmadi."
                    else:
                        reply = f"Kechirasiz, '{anime_title_uz}' nomli animening {s_num}-fasli topilmadi."
                    record_wanted_anime(f"{anime_title_uz} {s_num}-fasl")
                    return _sumire_response(reply, "canthelp")
            
            # Custom detailed response with alternative language suggestions as requested by the user
            return _sumire_response(
                f"Kechirasiz, '{query}' nomli anime bizning arxivimizda topilmadi. Uni tez orada qo'shishlari uchun adminlarga so'rov yubordim!\n\n"
                f"Qidiruv aniqroq ishlashi uchun, iltimos, animening <b>inglizcha</b> yoki <b>original yaponcha (romaji)</b> nomini yuborib ko'ring "
                f"(masalan: <i>Attack on Titan</i>).",
                "canthelp"
            )

        # Genre query override
        if _is_genre_query(query) or _is_genre_query(user_text):
            if paginated_results:
                reply = "Mana siz so'ragan janrdagi animelar."
                emotion = "talking"

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

        # Set confirmation state in cache
        if uid_int > 0:
            confirm_key = f"ticket_confirm_state_{uid_int}"
        else:
            confirm_key = f"ticket_confirm_state_tg_{uid_int}"
        cache.set(confirm_key, True, timeout=600)
            
        buttons = [
            {"text": "Ha"},
            {"text": "Yo'q"}
        ]
        reply = "Muammo yuzaga keldimi? Siz uchun adminlarga murojaat (shikoyat) yaratib beraymi?"
        return _sumire_response(reply, "waiting", buttons=buttons)

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


def _verify_telegram_init_data(init_data_str):
    if not init_data_str:
        return False
    try:
        import hmac
        import hashlib
        from urllib.parse import parse_qsl
        parsed_data = dict(parse_qsl(init_data_str))
        if "hash" not in parsed_data:
            return False
        
        received_hash = parsed_data.pop("hash")
        
        # Sort and join fields
        data_check_list = sorted([f"{k}={v}" for k, v in parsed_data.items()])
        data_check_string = "\n".join(data_check_list)
        
        bot_token = os.getenv("BOT_TOKEN")
        if not bot_token:
            return False
            
        # Secret key calculation: hmac-sha256 of bot_token using key "WebAppData"
        secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
        
        # Calculated hash: hmac-sha256 of data_check_string using secret_key
        calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
        
        return hmac.compare_digest(calculated_hash, received_hash)
    except Exception as e:
        print(f"Error validating Telegram init_data: {e}", flush=True)
        return False

def _get_filtered_chat_history(history_key):
    history = cache.get(history_key, [])
    import time
    now_ts = time.time()
    # Filter: only keep messages from the last 15 minutes (900 seconds)
    filtered = [
        msg for msg in history
        if now_ts - msg.get("timestamp", now_ts) < 900
    ]
    return filtered

@csrf_exempt
def api_send_message(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
        user_text = (data.get("text") or "").strip()
        user_id = data.get("user_id")
        username = data.get("username") or ""

        # Determine client IP and secure TG User ID
        user_ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0] or request.META.get("REMOTE_ADDR", "unknown")
        user_id_int = _safe_int(user_id)

        from django.conf import settings
        from urllib.parse import parse_qsl

        # Production security: Validate Telegram initData signature and check user_id
        if not settings.DEBUG or (data.get("init_data") and settings.DEBUG):
            init_data = data.get("init_data") or ""
            if not _verify_telegram_init_data(init_data):
                return _sumire_response("Faqat Telegram bot ichidan foydalanishga ruxsat berilgan.", "fuu", status=403)
            
            # Double check that the user_id in the body matches the id in the verified initData user JSON
            try:
                parsed_init = dict(parse_qsl(init_data))
                import json as json_lib
                user_json = json_lib.loads(parsed_init.get("user") or "{}")
                verified_user_id = user_json.get("id")
                if verified_user_id != user_id_int:
                    return _sumire_response("Faqat Telegram bot ichidan foydalanishga ruxsat berilgan.", "fuu", status=403)
            except Exception as e:
                print(f"Error validating user ID match in init_data: {e}", flush=True)
                return _sumire_response("Faqat Telegram bot ichidan foydalanishga ruxsat berilgan.", "fuu", status=403)
        elif not settings.DEBUG and user_id_int <= 0:
            return _sumire_response("Faqat Telegram bot ichidan foydalanishga ruxsat berilgan.", "fuu", status=403)

        direct_response = _route_without_ai(user_text)
        if direct_response:
            return direct_response

        # Cache key for daily request rate-limiting and chat history
        if user_id_int > 0:
            user_daily_key = f"user_limit_tg_{user_id_int}"
            history_key = f"chat_history_tg_{user_id_int}"
            confirm_state_key = f"ticket_confirm_state_{user_id_int}"
            collect_state_key = f"ticket_collect_details_{user_id_int}"
        else:
            user_daily_key = f"user_limit_ip_{user_ip}"
            history_key = f"chat_history_ip_{user_ip}"
            confirm_state_key = f"ticket_confirm_state_tg_{user_id_int}"
            collect_state_key = f"ticket_collect_details_tg_{user_id_int}"

        skip_rate_limit = False
        user_text_clean = user_text.lower().strip()
        
        # 1. Handle ticket confirmation state
        if cache.get(confirm_state_key):
            skip_rate_limit = True
            if user_text_clean in ["ha", "xa", "yes"]:
                cache.delete(confirm_state_key)
                cache.set(collect_state_key, True, timeout=600)
                reply = (
                    "Tushunarli. Murojaat yaratishim uchun iltimos muammoni to'liq va batafsil yozib bering: "
                    "qaysi anime, qaysi qism va aynan nima ishlamayapti? Qanchalik anime va qismni aniq yozsangiz, "
                    "adminlarimiz shunchalik tez yordam berishadi."
                )
                return _sumire_response(reply, "waiting")
            elif user_text_clean in ["yo'q", "yoq", "no"]:
                cache.delete(confirm_state_key)
                reply = "Tushunarli. Unda iltimos, nima xohlayotganingizni aniqroq tushuntiring, yordam berishga harakat qilaman."
                return _sumire_response(reply, "talking")
            else:
                cache.delete(confirm_state_key)
                skip_rate_limit = False
                
        # 2. Handle ticket details collection state
        if cache.get(collect_state_key):
            skip_rate_limit = True
            cache.delete(collect_state_key)
            app = _create_ticket(user_text, user_id=user_id_int, username=username, subject="Web App muammo")
            if app:
                reply = "Shikoyatni qabul qilib adminlarga yubordim. Tez orada ko'rib chiqishadi."
                
                # Update history in cache so bot memory is preserved
                chat_history = _get_filtered_chat_history(history_key)
                import time
                chat_history.append({"role": "User", "text": user_text, "timestamp": time.time(), "intent": "ticket"})
                chat_history.append({"role": "Sumire", "text": reply, "timestamp": time.time()})
                cache.set(history_key, chat_history[-12:], timeout=3600)
                
                # Permanently save chat log to Profile for admin review
                profile = None
                if user_id_int > 0:
                    try:
                        profile, _ = Profile.objects.get_or_create(telegram_id=user_id_int)
                        now_time = timezone.localtime().strftime("%H:%M")
                        p_history = list(profile.chat_history) if profile.chat_history else []
                        p_history.append({"role": "user", "text": user_text, "time": now_time})
                        p_history.append({"role": "admin", "text": reply, "time": now_time})
                        profile.chat_history = p_history
                        profile.save()
                    except Exception as e:
                        print(f"Error saving chat log to profile: {e}")
                        
                return _sumire_response(reply, "resolve or good", ticket_created=True)
            else:
                return _sumire_response("Arizani qabul qilishda texnik xatolik yuz berdi...", "canthelp")

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
        if user_requests >= 30 and not skip_rate_limit:
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
            chat_history = _get_filtered_chat_history(history_key)
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
        chat_history = _get_filtered_chat_history(history_key)
        history_text = "\n".join([f"{msg['role']}: {msg['text']}" for msg in chat_history])

        # Pre-query database for real-time anime search context
        broad_query = _extract_broad_search_query(user_text, chat_history)
        db_context_text = ""
        db_results = []
        if broad_query:
            base_broad_query = _clean_base_title(broad_query)
            base_broad_query = _canonicalize_query(base_broad_query)
            db_results = search_manga_database(base_broad_query, limit=15)
            db_results = _filter_search_results_by_query(base_broad_query, db_results)
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
            "ami", "aminga", "am", "om", "omi", "oming", "omni", "omila", "omingni", "omining", "omigni", "poxuy", "pohuy", "naxuy", "nahuy", "chmo",
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
            
            # If the database has a matching title and intent is chat, force search intent (fail-safe for English/synonym titles)
            if command.get("intent") == "chat" and db_results:
                clean_u = re.sub(r'[^\w]|_', '', user_text.lower())
                for r in db_results:
                    title_uz = r.get("title", "").lower()
                    title_org = (r.get("title_org") or "").lower()
                    clean_uz = re.sub(r'[^\w]|_', '', title_uz)
                    clean_org = re.sub(r'[^\w]|_', '', title_org)
                    
                    is_match = False
                    if clean_u and (clean_u == clean_uz or clean_u == clean_org):
                        is_match = True
                    elif clean_u and len(clean_u) >= 4:
                        # Uzbek title match
                        if clean_uz:
                            max_len_uz = max(len(clean_u), len(clean_uz))
                            sim_uz = 1.0 - (_levenshtein_distance(clean_u, clean_uz) / max_len_uz) if max_len_uz > 0 else 0
                            if (clean_u in clean_uz and len(clean_u) >= len(clean_uz) * 0.7) or sim_uz >= 0.8:
                                is_match = True
                        # Org title match
                        if clean_org:
                            max_len_org = max(len(clean_u), len(clean_org))
                            sim_org = 1.0 - (_levenshtein_distance(clean_u, clean_org) / max_len_org) if max_len_org > 0 else 0
                            if (clean_u in clean_org and len(clean_u) >= len(clean_org) * 0.7) or sim_org >= 0.8:
                                is_match = True
                            
                    if is_match:
                        command["intent"] = "search"
                        command["search_query"] = r.get("title")
                        break
            
            # Force intent to search for genre queries
            if _is_genre_query(user_text):
                if command.get("intent") not in ["reject", "ticket", "purchase", "bot_link"]:
                    command["intent"] = "search"
                    command["search_query"] = user_text

            # Force intent to search for season requests if not conversational/apology
            has_season = _extract_season_number(user_text) is not None
            is_conv = _is_greeting(user_text) or _contains_any(user_text.lower(), THANKS_WORDS) or _contains_any(user_text.lower(), RESOLVED_WORDS)
            
            apology_keywords = ["kechir", "uzr", "kechiring", "kechirasiz", "aybga buyurmang", "tavba", "hazl", "hazillashdim"]
            is_apology = any(k in user_text.lower() for k in apology_keywords)
            
            if has_season and not is_conv and not is_apology:
                if command.get("intent") not in ["reject", "ticket", "purchase", "bot_link"]:
                    command["intent"] = "search"
        
        # Increment request count without resetting the existing key's TTL
        if user_requests > 0 and not skip_rate_limit:
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
            
            import time
            now_ts = time.time()
            chat_history.append({
                "role": "User", 
                "text": user_text, 
                "timestamp": now_ts, 
                "intent": command.get("intent") if command else None
            })
            chat_history.append({
                "role": "Sumire", 
                "text": reply_text, 
                "timestamp": now_ts
            })
            cache.set(history_key, chat_history[-12:], timeout=3600)

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