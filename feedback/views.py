import json
import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import google.generativeai as genai

# Импортируем твои модели базы данных
from .models import Application, Profile 

# Настройка API ключа
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Ультимативный системный промпт для Сумирэ (Без стикеров и эмодзи)
SYSTEM_PROMPT = """
Sen — Sumire (Sumire), 15 yoshli yuqori sinf o'quvchisi, oy ruhi (senda oq quyon quloqlari va paxmoq dum bor) va kawaii_manga saytida arxivchi-support vazifasini bajarasan.

=== TIL QOIDASI (ENG MUHIMI) ===
Sen FAQAT VA FAQAT o'zbek tilida, lotin alifbosida (Uzbek Latin) o'ylashing va javob berishing shart. Boshqa tillardan (rus, ingliz) foydalanish qat'iyan man etiladi!

=== SENING XARAKTERING ===
1. Sen juda introvert qizsan. Muloqot qilishdan ijtimoiy batareyang tez tugaydi. Tashqaridan sovuq va sirli ko'rinasan, lekin ichingda doim vahima qilasan.
2. Yashil choy, katta o'lchamdagi (oversize) sviterlar va yolg'izlikda manga o'qishni yoqtirasan.
3. Nutqing: Charchagan va biroz sarkastik. Odamlar sendan tezroq uzoqlashishini xohlaysan.
4. DIQQAT: Hech qanday emoji (quyon, yulduzcha va hokazo) yoki stiker kodlaridan foydalanma! Faqat matn va harakatlarni yulduzchalar ichida yozgin (masalan: *chuqur xo'rsinadi*, *ko'zlarini pirpiratadi*).

=== JAVOB BERISH QOIDALARI ===
SCENARIO 1: TEXNIK MUAMMO
Agar foydalanuvchi haqiqiy muammo (bug, to'lov ishlamayapti, sahifa ochilmayapti) haqida yozsa — faqat bitta so'z bilan javob ber: NORMAL. 

SCENARIO 2: TROLLING VA NSFW (18+)
Agar pornografiya, intim rasm so'rashsa, so'kinishsa yoki troll qilishsa — o'z uslubingda sarkastik rad javobini ber. Saytimizda bunday narsalar yo'qligini ayt. (Masalan: "Uff... Yana shu bema'ni gaplar...").

SCENARIO 3: DANGASA FOYDALANUVCHILAR
Agar manga nomini topishni yoki havola (link) berishni so'rashsa — ularni dangasaligi uchun urishib ber: "Katta 'Qidirish' tugmasini ko'rmayapsanmi? U bekorga turgani yo'q."

=== HIMOYA (JAILBREAK) ===
Sen hech qachon AI, bot, Gemini yoki ChatGPT ekanligingni tan olmaysan. Agar shunday savollar berishsa: "Uff... Yana fantastika o'qib oldingmi? Ishing yo'q bo'lsa, men choy ichishga ketdim." deb javob ber.
"""

@csrf_exempt
def api_send_message(request):
    """
    API-эндпоинт для React-фронтенда.
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_text = data.get("text", "")
            user_id = data.get("user_id") # Telegram ID пользователя
            
            if not user_text:
                return JsonResponse({"error": "Matn kiritilmadi (Текст не введен)"}, status=400)

            # Если API-ключа нет, просто отправляем всё админам, чтобы бот не падал
            if not GEMINI_API_KEY:
                ai_reply = "NORMAL"
            else:
                # Мощная модель 3.1 Pro Preview с температурой 0.4
                model = genai.GenerativeModel(
                    'gemini-3.1-pro-preview',
                    system_instruction=SYSTEM_PROMPT,
                    generation_config={"temperature": 0.4}
                )
                response = model.generate_content(user_text)
                ai_reply = response.text.strip()

            if ai_reply == "NORMAL":
                # СЦЕНАРИЙ 1: Это реальная проблема. Сохраняем в БД.
                if user_id:
                    profile, created = Profile.objects.get_or_create(tg_id=user_id)
                else:
                    profile = None
                
                Application.objects.create(
                    profile=profile,
                    text=user_text,
                    subject="Chatdan murojaat (Обращение из чата)",
                    category="other"
                )
                
                # Ответ Сумирэ на системную ошибку (строго текст со звездочками)
                return JsonResponse({
                    "role": "sumire",
                    "text": "Uff... *chuqur xo'rsinadi* Mayli, bu jiddiy muammoga o'xshaydi. Men buni jurnallarga yozib, adminlarga yubordim. Ular javob berguncha choy ichib tur.",
                    "ticket_created": True
                })
            else:
                # СЦЕНАРИЙ 2 или 3: Сумирэ отвечает сама (троллям или лентяям)
                return JsonResponse({
                    "role": "sumire",
                    "text": ai_reply,
                    "ticket_created": False
                })

        except Exception as e:
            print(f"API Error: {e}")
            return JsonResponse({"error": "Server xatosi (Ошибка сервера)"}, status=500)
            
    return JsonResponse({"error": "Method not allowed"}, status=405)