import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from feedback.models import Profile

profiles = Profile.objects.all()
print(f"TOTAL PROFILES FOUND: {profiles.count()}")
for p in profiles:
    print(f"TELEGRAM ID: {p.telegram_id}, USERNAME: {p.telegram_id}")
    history = p.chat_history or []
    print(f"  History length: {len(history)}")
    for msg in history[-8:]:
        print(f"    {msg.get('role')}: {msg.get('text')} ({msg.get('time')})")
