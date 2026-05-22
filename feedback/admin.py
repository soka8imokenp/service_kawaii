from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Application, Message, Profile

class ProfileAdminForm(forms.ModelForm):
    username = forms.CharField(label="Admin nick", max_length=150, required=False)
    password = forms.CharField(
        label="Parol",
        required=False,
        widget=forms.PasswordInput(render_value=True),
        help_text="Yangi admin yaratishda majburiy. Mavjud admin uchun bo'sh qoldirsangiz parol o'zgarmaydi.",
    )
    is_owner = forms.BooleanField(
        label="Главный admin (superuser)",
        required=False,
        help_text="Yoqilsa admin Django'da ham superuser bo'ladi.",
    )

    class Meta:
        model = Profile
        fields = ("telegram_id", "favorite_genres")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Безопасная инициализация полей, если профиль привязан к Django User
        if self.instance and self.instance.pk and hasattr(self.instance, 'user') and self.instance.user:
            self.fields["username"].initial = self.instance.user.username
            self.fields["is_owner"].initial = self.instance.user.is_superuser

    def clean_username(self):
        username = self.cleaned_data.get("username", "").strip()
        if not username:
            return username

        User = get_user_model()
        qs = User.objects.filter(username=username)
        if self.instance and self.instance.pk and hasattr(self.instance, 'user') and self.instance.user:
            qs = qs.exclude(pk=self.instance.user.pk)

        if qs.exists():
            raise forms.ValidationError("Bunday username allaqachon mavjud.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get("username")
        password = cleaned_data.get("password")

        # Если задан никнейм (создаем админа), но забыли пароль
        if username and not self.instance.pk and not password:
            self.add_error("password", "Yangi admin uchun parol kiriting.")

        return cleaned_data

    def save(self, commit=True):
        username = self.cleaned_data.get("username", "").strip()
        password = self.cleaned_data.get("password")
        is_owner = self.cleaned_data.get("is_owner", False)

        profile = super().save(commit=False)

        if username:
            User = get_user_model()
            # Если у профиля уже есть юзер — обновляем
            if self.instance and self.instance.pk and hasattr(self.instance, 'user') and self.instance.user:
                user = self.instance.user
                user.username = username
            else:
                user = User(username=username, email=f"{username}@example.com")

            user.is_staff = True
            user.is_superuser = is_owner

            if password:
                user.set_password(password)

            user.save()
            profile.user = user
        else:
            # Если имя пользователя стерли или не ввели (обычный клиент Mini App)
            # Отвязываем Django User, если он был
            if self.instance and self.instance.pk and hasattr(self.instance, 'user') and self.instance.user:
                profile.user = None

        if commit:
            profile.save()

        return profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    form = ProfileAdminForm
    list_display = ("telegram_id", "admin_username", "admin_role", "favorite_genres")
    search_fields = ("telegram_id", "favorite_genres", "user__username")
    list_filter = ("user__is_superuser", "user__is_staff")
    
    # Группируем поля в режиме редактирования профиля
    fieldsets = (
        ("Asosiy ma'lumotlar", {"fields": ("telegram_id", "favorite_genres")}),
        ("Admin huquqlari (Faqat xodimlar uchun)", {"fields": ("username", "password", "is_owner")}),
    )

    def admin_username(self, obj):
        if hasattr(obj, 'user') and obj.user:
            return obj.user.username
        return "Mijoz (User)"

    admin_username.short_description = "Nick"

    def admin_role(self, obj):
        if hasattr(obj, 'user') and obj.user:
            return "Owner" if obj.user.is_superuser else "Admin"
        return "Foydalanuvchi"

    admin_role.short_description = "Role"    


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("created_at",)
    fields = ("text", "is_from_admin", "created_at")


class ApplicationAdminForm(forms.ModelForm):
    admin_reply_field = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "style": "width: 100%; border: 2px solid #444; border-radius: 8px; padding: 10px;",
                "placeholder": "Mijozga xabar yozing...",
            }
        ),
        required=False,
        label="Admin javobi",
    )

    class Meta:
        model = Application
        fields = "__all__"


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    form = ApplicationAdminForm
    inlines = [MessageInline]

    list_display = ("subject", "username", "category", "is_answered", "is_closed", "created_at")
    list_filter = ("is_closed", "category", "is_answered")
    readonly_fields = ("chat_history", "created_at", "updated_at")

    fieldsets = (
        ("Asosiy ma'lumotlar", {"fields": ("user_id", "username", "category", "subject", "is_closed", "is_answered")}),
        ("Legacy Chat (JSON)", {"fields": ("chat_history",)}),
        (
            "Javob berish",
            {
                "fields": ("admin_reply_field",),
                "description": "Bu yerga yozilgan xabar Web App ichidagi chatda paydo bo'ladi.",
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        reply_text = form.cleaned_data.get("admin_reply_field")
        
        if reply_text:
            new_message = {"role": "admin", "text": reply_text, "time": timezone.now().strftime("%H:%M")}

            history = list(obj.chat_history) if obj.chat_history else []
            history.append(new_message)
            obj.chat_history = history
            
            obj.is_answered = True

            # Также автоматически дублируем сообщение в связанную модель Message для истории
            Message.objects.create(
                application=obj,
                text=reply_text,
                is_from_admin=True
            )

        super().save_model(request, obj, form, change)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("application", "is_from_admin", "created_at")
    list_filter = ("is_from_admin", "created_at")
    search_fields = ("application__subject", "application__username", "text")