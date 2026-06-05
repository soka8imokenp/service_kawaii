import os
import django
import json

os.environ['DATABASE_URL'] = 'sqlite:///db.sqlite3'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from feedback.views import _parse_ai_command, _extract_broad_search_query, search_manga_database

def test_step(user_text, history):
    history_text = "\n".join([f"{msg['role']}: {msg['text']}" for msg in history])
    broad_query = _extract_broad_search_query(user_text, history)
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
        
    print(f"\nUSER: '{user_text}'")
    print(f"BROAD_QUERY: '{broad_query}'")
    print(f"DB CONTEXT:\n{db_context_text}")
    
    cmd = _parse_ai_command(user_text, history_text, None, db_context_text)
    print("AI COMMAND:")
    print(json.dumps(cmd, indent=2))
    
    # Simulate reply text
    reply_text = cmd.get("reply", "")
    history.append({"role": "User", "text": user_text})
    history.append({"role": "Sumire", "text": reply_text})

history = []
test_step("Jozibali taomlar mabudasi 2fasli kerak", history)
test_step("Animey Jozibali taomlar mabudasi 2fasli ketak", history)
