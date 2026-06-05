import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from feedback.models import Profile

profiles = Profile.objects.all()
print(f"TOTAL PROFILES: {profiles.count()}")
for p in profiles:
    history = p.chat_history or []
    if len(history) > 0:
        print(f"=== PROFILE: {p.telegram_id} | User: {p} ===")
        # Print last 40 messages to see full context of their interactions
        for msg in history[-40:]:
            role = msg.get('role', 'unknown')
            text = msg.get('text', '')
            search_query = msg.get('search_query', None)
            cached_results = msg.get('cached_results', None)
            print(f"  {role}: {text}")
            if search_query:
                print(f"    [search_query: {search_query}]")
            if cached_results:
                print(f"    [cached_results count: {len(cached_results)}]")
        print("-" * 50)
        print()
