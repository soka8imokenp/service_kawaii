import json
from django.core.management.base import BaseCommand
from feedback.models import Application, Profile, Message

class Command(BaseCommand):
    help = 'Analyze user logs, arizalar (applications), and profiles'

    def handle(self, *args, **options):
        # 1. Total Stats
        apps = Application.objects.all().order_by('-created_at')
        profiles = Profile.objects.all()
        messages = Message.objects.all().order_by('created_at')
        
        self.stdout.write(f"=== DATABASE STATS ===")
        self.stdout.write(f"Total Profiles: {profiles.count()}")
        self.stdout.write(f"Total Applications (Arizalar): {apps.count()}")
        self.stdout.write(f"Total Messages: {messages.count()}")
        self.stdout.write("")
        
        # 2. Detailed Profile Analysis
        self.stdout.write("=== PROFILES ===")
        for p in profiles[:15]:
            self.stdout.write(f"Profile Telegram ID: {p.telegram_id}")
            self.stdout.write(f"Favorite Genres: {p.favorite_genres}")
            self.stdout.write(f"Chat History length: {len(p.chat_history) if p.chat_history else 0}")
            self.stdout.write("-" * 30)
        self.stdout.write("")
        
        # 3. Application / Chats Analysis
        self.stdout.write("=== APPLICATIONS & CHATS ===")
        for app in apps[:30]:
            self.stdout.write(f"Application #{app.id} | User: {app.username} | Subject: {app.subject} | Category: {app.category}")
            self.stdout.write(f"Status: Answered={app.is_answered}, Closed={app.is_closed}")
            self.stdout.write(f"Created: {app.created_at}")
            
            # Print messages for this application
            app_messages = messages.filter(application_id=app.id)
            if app_messages.exists():
                self.stdout.write("Messages:")
                for msg in app_messages:
                    sender = "Admin" if msg.is_from_admin else "User"
                    self.stdout.write(f"  [{sender} - {msg.created_at}]: {msg.text}")
            
            # Print chat history field
            if app.chat_history:
                self.stdout.write("Chat History (JSON/Text):")
                try:
                    if isinstance(app.chat_history, str):
                        history = json.loads(app.chat_history)
                    else:
                        history = app.chat_history
                    
                    if isinstance(history, list):
                        for item in history:
                            role = item.get('role', 'unknown')
                            text = item.get('text', '') or item.get('content', '')
                            self.stdout.write(f"  [{role}]: {text}")
                    else:
                        self.stdout.write(f"  Raw: {history}")
                except Exception as e:
                    self.stdout.write(f"  Error parsing history: {e}")
                    self.stdout.write(f"  Raw: {app.chat_history[:200]}")
            self.stdout.write("=" * 50)
