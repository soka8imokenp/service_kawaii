import json
import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import google.generativeai as genai

# Sening baza modellaring
from .models import Application, Profile 
# from manga.models import Manga # KELAJAKDA MANGA BAZANGNI SHU YERDAN CHAQIRASAN

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    # .strip() удалит все случайные пробелы и невидимые переносы строк по краям
    genai.configure(api_key=GEMINI_API_KEY.strip())

# =================================================================
# 1-QADAM: AI UCHUN ASBOB (TOOL / FUNCTION) YARATAMIZ
# =================================================================
def search_manga_database(query: str, limit: int = 3) -> str:
    """
    Ma'lumotlar bazasidan manga yoki animelarni qidirish uchun funksiya.
    Foydalanuvchi biror janr, nom yoki tavsiya so'rasa, shu funksiyadan foydalaniladi.
    """
    # HOZIRCHA BU YERDA FAKE (YASAMA) BAZA TURIBDI.
    # Kelajakda bu yerni o'z Django bazang bilan almashtirasan:
    # results = Manga.objects.filter(title__icontains=query)[:limit]
    
    # AI ga tushunarli bo'lishi uchun natijani JSON string ko'rinishida qaytaramiz
    fake_db_results = [
        {"title": f"{query} sarguzashtlari", "link": "https://kawaii-manga.uz/manga/1"},
        {"title": f"Qorong'u {query}", "link": "https://kawaii-manga.uz/manga/2"},
        {"title": f"{query} romantikasi", "link": "https://kawaii-manga.uz/manga/3"}
    ]
    return json.dumps(fake_db_results)


# =================================================================
# 2-QADAM: MUKAMMAL SYSTEM PROMPT VA JSON FORMAT KELISHUVI
# =================================================================
SYSTEM_PROMPT = """
Sen — Sumire, 15 yoshli yuqori sinf o'quvchisi, oy ruhi va kawaii_manga saytida arxivchisan.

=== TIL QOIDASI ===
Faqat o'zbek tilida, lotin alifbosida o'ylaysan va yozasan. Boshqa tillar qat'iyan man etiladi!

=== SENING XARAKTERING ===
1. Sovuq, biroz sarkastik, introvert qizsan. 
2. Hech qanday emoji ishlatma! Harakatlarni *yulduzchalar* ichida yoz (*xo'rsinadi*, *ko'zlarini pirpiratadi*).

=== VAZIFALAR ===
1. TEXNIK MUAMMO: Agar haqiqiy xatolik, bug yoki to'lov haqida yozishsa, matnga faqat "NORMAL" deb yoz.
2. TROLLING: So'kinish yoki 18+ narsalarga sarkastik rad javobini ber.
3. MANGA QIDIRISH: Agar foydalanuvchi tavsiya so'rasa, albatta `search_manga_database` funksiyasidan foydalan! Topilgan ma'lumotlarni chiroyli qilib aytib ber va havolalarni (link) javobingga qistirma qilib qo'sh.

=== JAVOB FORMATI (ENG MUHIMI) ===
Sening har bir javobing FAQAT JSON formatida bo'lishi shart! Quyidagi strukturaga qat'iy amal qil:
{
    "text": "Sening matning...",
    "emotion": "talking"
}

"emotion" uchun quyidagi so'zlardan vaziyatga mosini tanla (boshqa so'z ishlatma):
canthelp, face palm, fuu, hmmm, resolve or good, shocked, shy, talking, think, ty, waiting, what
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
            user_id = data.get("user_id")
            
            if not user_text:
                return JsonResponse({"error": "Matn kiritilmadi"}, status=400)

            if not GEMINI_API_KEY:
                return JsonResponse({"error": "API kalit o'rnatilmagan"}, status=500)

            # =================================================================
            # 3-QADAM: GEMINI MODELINI SOZLASh (TOOLS VA JSON BILAN)
            # =================================================================
            # E'tibor ber: gemini-1.5-pro modeli function calling uchun eng barqarori hisoblanadi
            model = genai.GenerativeModel(
                model_name='gemini-flash-lite-latest', 
                system_instruction=SYSTEM_PROMPT,
                tools=[search_manga_database], # FUNKSIYANI SHU YERDA BERAMIZ
                generation_config=genai.GenerationConfig(
                    temperature=0.4,
                    response_mime_type="application/json", # AI dan doim JSON talab qilamiz!
                )
            )

            # start_chat(enable_automatic_function_calling=True) - bu haqiqiy mo'jiza!
            # AI qachon bazaga kirishni o'zi hal qiladi va orqa fonda funksiyani o'zi chaqirib javobni oladi.
            chat = model.start_chat(enable_automatic_function_calling=True)
            response = chat.send_message(user_text)
            
            # AI dan kelgan JSON javobni Python dictionary'ga o'giramiz
            ai_data = json.loads(response.text)
            ai_reply = ai_data.get("text", "").strip()
            ai_emotion = ai_data.get("emotion", "talking")

            # -----------------------------------------------------------------
            # SCENARIO 1: Texnik muammo
            # -----------------------------------------------------------------
            if "NORMAL" in ai_reply:
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
                
                return JsonResponse({
                    "role": "sumire",
                    "text": "Uff... *chuqur xo'rsinadi* Mayli, bu jiddiy muammoga o'xshaydi. Men buni jurnallarga yozib, adminlarga yubordim. Ular javob berguncha choy ichib tur.",
                    "emotion": "face palm", # Texnik xatoda doim face palm qiladi!
                    "ticket_created": True
                })
            
            # -----------------------------------------------------------------
            # SCENARIO 2 & 3: Normal suhbat yoki bazadan izlash natijasi
            # -----------------------------------------------------------------
            else:
                return JsonResponse({
                    "role": "sumire",
                    "text": ai_reply,
                    "emotion": ai_emotion, # Front-end'dagi React kodimiz buni ushlab papkani o'zgartiradi!
                    "ticket_created": False
                })

        except Exception as e:
            print(f"API Error: {e}")
            return JsonResponse({
                "role": "sumire",
                "text": "Aloqa uzildi... *asabiy kompyuterni taqillatadi* Serverda qandaydir xatolik.",
                "emotion": "canthelp",
                "ticket_created": False
            }, status=500)
            
    return JsonResponse({"error": "Method not allowed"}, status=405)