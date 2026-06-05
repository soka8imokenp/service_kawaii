import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from feedback.models import Profile

profiles = Profile.objects.all()
for p in profiles:
    print(f"TELEGRAM ID: {p.telegram_id}")
    history = p.chat_history or []
    for msg in history[-10:]:
        print(f"  {msg.get('role')}: {msg.get('text')} ({msg.get('time')})")
