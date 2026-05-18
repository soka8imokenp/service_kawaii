import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()
username = 'admin'
password = 'devve08082002' # Укажи свой пароль

user = User.objects.filter(username=username).first()

if not user:
    User.objects.create_superuser(username, 'admin@example.com', password)
    print(f"--- Admin '{username}' created! ---")
else:
    # ПРИНУДИТЕЛЬНО обновляем пароль и права, если он уже есть
    user.set_password(password)
    user.is_superuser = True
    user.is_staff = True
    user.save()
    print(f"--- Admin '{username}' updated and fixed! ---")