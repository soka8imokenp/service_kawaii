import os
import django
import json

if 'DATABASE_URL' not in os.environ:
    os.environ['DATABASE_URL'] = 'sqlite:///db.sqlite3'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.test import RequestFactory
from feedback.views import api_send_message
from django.core.cache import cache

factory = RequestFactory()

def send_msg(user_id, text):
    data = {"user_id": user_id, "text": text, "username": "test_user"}
    req = factory.post("/feedback/api/send/", data=json.dumps(data), content_type="application/json")
    req.META["REMOTE_ADDR"] = "127.0.0.1"
    
    # We will temporarily monkeypatch _filter_search_results_by_query to trace it
    import feedback.views as views
    old_filter = views._filter_search_results_by_query
    old_execute = views._execute_ai_command
    
    def traced_execute(*args, **kwargs):
        res = old_execute(*args, **kwargs)
        return res
        
    def traced_filter(query, results):
        print(f"    [traced_filter] Input Query: '{query}'")
        print(f"    [traced_filter] Input Results: {[r['title'] for r in results]}")
        res = old_filter(query, results)
        print(f"    [traced_filter] Output Filtered: {[r['title'] for r in res]}")
        return res
        
    views._filter_search_results_by_query = traced_filter
    try:
        resp = api_send_message(req)
    finally:
        views._filter_search_results_by_query = old_filter
        
    print(f"\n--- USER: '{text}' ---")
    print(f"STATUS: {resp.status_code}")
    content = json.loads(resp.content.decode('utf-8'))
    print(f"SUMIRE: '{content.get('text')}'")
    anime_list = content.get('anime_list', [])
    if anime_list:
        print("ANIME LIST:")
        for a in anime_list[:5]:
            print(f"  - Name: {a['name']} | URL: {a['url']}")
    else:
        print("ANIME LIST: Empty")

uid = 123456789
# Clear history cache to start fresh
cache.delete(f"chat_history_tg_{uid}")
cache.delete(f"user_limit_tg_{uid}")

from feedback.models import Profile
Profile.objects.filter(telegram_id=uid).delete()

# Run the exact sequence
send_msg(uid, "Yoq man mabud minorasi haqida")
send_msg(uid, "Oxirgi fasli qaysi")
send_msg(uid, "Ikkalasini tasha unda")
