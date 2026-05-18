import os
import requests
from django.db import models
from django.contrib.auth.models import User


class Profile(models.Model):
    """Связка Django-пользователя с Telegram ID."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    telegram_id = models.BigIntegerField(unique=True, db_index=True)

    class Meta:
        verbose_name = "Profil"
        verbose_name_plural = "Profillar"

    def __str__(self):
        return f"@{self.user.username} ({self.telegram_id})"

class Application(models.Model):
    TYPES = [
        ('news', 'Yangilik yuborish'),
        ('ads', 'Reklama joylashtirish'),
        ('report', 'Shikoyat qilish'),
        ('collab', 'Hamkorlik'),
        ('other', 'Boshqa'),
    ]

    user_id = models.BigIntegerField(verbose_name="User ID")
    username = models.CharField(max_length=150, null=True, blank=True, verbose_name="Username")
    category = models.CharField(max_length=20, choices=TYPES, verbose_name="Kategoriya")
    subject = models.CharField(max_length=50, verbose_name="Mavzu", default="Mavzu ko'rsatilmadi")
    
    chat_history = models.JSONField(default=list, verbose_name="Chat tarixi", blank=True)
    
    is_answered = models.BooleanField(default=False, verbose_name="Javob berildi")
    is_closed = models.BooleanField(default=False, verbose_name="Yopilgan")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yuborilgan vaqt")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Oxirgi o'zgarish")

    class Meta:
        verbose_name = "Ariza"
        verbose_name_plural = "Arizalar"
        ordering = ['is_closed', '-updated_at']

    def __str__(self):
        status = "✅" if self.is_closed else "📩"
        return f"{status} [{self.category}] {self.subject} - @{self.username}"

    def save(self, *args, **kwargs):
        # Проверка на обновление существующей записи
        if self.pk:
            try:
                old_obj = Application.objects.get(pk=self.pk)
                # Если в историю добавлено новое сообщение
                if len(self.chat_history) > len(old_obj.chat_history):
                    last_msg = self.chat_history[-1]
                    # Только если автор сообщения — админ
                    if last_msg.get('role') == 'admin':
                        self.is_answered = True
                        self.send_telegram_notification()
            except Application.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)

    def send_telegram_notification(self):
        """Простое текстовое уведомление без кнопок"""
        token = os.getenv("BOT_TOKEN")
        if not token:
            return

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        
        message_text = (
            f"🌸 <b>Sizning murojaatingizga javob berildi!</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"<b>Mavzu:</b> {self.subject}\n\n"
            f"Javobni o'qish uchun bot menyusidagi ilovani oching."
        )

        payload = {
            "chat_id": self.user_id,
            "text": message_text,
            "parse_mode": "HTML"
        }

        try:
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print(f"Telegram notification error: {e}")


class Message(models.Model):
    """Нормализованная история сообщений по тикету."""
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='messages')
    text = models.TextField(verbose_name="Xabar")
    is_from_admin = models.BooleanField(default=False, verbose_name="Admindan")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yuborilgan vaqt")

    class Meta:
        verbose_name = "Xabar"
        verbose_name_plural = "Xabarlar"
        ordering = ["created_at"]

    def __str__(self):
        sender = "ADMIN" if self.is_from_admin else "USER"
        return f"{sender} #{self.application_id}: {self.text[:40]}"