import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from feedback.models import Profile

p = Profile.objects.get(telegram_id=6947059631)
history = p.chat_history or []
for msg in history:
    print(f"role: {msg.get('role')}")
    print(f"  text: {msg.get('text')}")
    print(f"  search_query: {msg.get('search_query')}")
    print(f"  intent: {msg.get('intent')}")
    print(f"  cached_results: {msg.get('cached_results')}")
