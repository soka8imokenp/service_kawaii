from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Application, Message, Profile

class ProfileAdminForm(forms.ModelForm):
    username = forms.CharField(label="Admin nick", max_length=150)
    password = forms.CharField(
        label="Parol",
        required=False,
        widget=forms.PasswordInput(render_value=True),
        help_text="Yangi admin yaratishda majburiy. Mavjud admin uchun bo'sh qoldirsangiz parol o'zgarmaydi.",
    )
    is_owner = forms.BooleanField(
        label="Главный админ (superuser)",
        required=False,
        help_text="Yoqilsa admin Django'da ham superuser bo'ladi.",
    )

    class Meta:
        model = Profile
        fields = ("telegram_id",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.user_id:
            self.fields["username"].initial = self.instance.user.username
            self.fields["is_owner"].initial = self.instance.user.is_superuser

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        User = get_user_model()

        qs = User.objects.filter(username=username)
        if self.instance and self.instance.pk and self.instance.user_id:
            qs = qs.exclude(pk=self.instance.user_id)

        if qs.exists():
            raise forms.ValidationError("Bunday username allaqachon mavjud.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")

        if not self.instance.pk and not password:
            self.add_error("password", "Yangi admin uchun parol kiriting.")

        return cleaned_data

    def save(self, commit=True):
        User = get_user_model()
        username = self.cleaned_data["username"]
        password = self.cleaned_data.get("password")
        is_owner = self.cleaned_data.get("is_owner", False)

        if self.instance and self.instance.pk and self.instance.user_id:
            user = self.instance.user
            user.username = username
        else:
            user = User(username=username, email=f"{username}@example.com")

        user.is_staff = True
        user.is_superuser = is_owner

        if password:
            user.set_password(password)

        user.save()

        profile = super().save(commit=False)
        profile.user = user

        if commit:
            profile.save()

        return profile



@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    form = ProfileAdminForm
    list_display = ("telegram_id", "admin_username", "admin_role")
    search_fields = ("user__username", "telegram_id")
    readonly_fields = ("user",)

    def admin_username(self, obj):
        return obj.user.username

    admin_username.short_description = "Nick"

    def admin_role(self, obj):
        return "Owner" if obj.user.is_superuser else "Admin"

    admin_role.short_description = "Role"    
    


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("created_at",)
    fields = ("text", "is_from_admin", "created_at")

# 1. Создаем правильную форму для админки с нашим кастомным полем
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


# 2. Подключаем форму в админку
class ApplicationAdmin(admin.ModelAdmin):
    # Указываем Django использовать нашу форму!
    form = ApplicationAdminForm
    inlines = [MessageInline]

    list_display = ("subject", "username", "category", "is_answered", "is_closed", "created_at")
    list_filter = ("is_closed", "category", "is_answered")

    readonly_fields = ("chat_history", "created_at", "updated_at")

    
    # Группировка полей
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

    # Логика сохранения
    def save_model(self, request, obj, form, change):
        reply_text = form.cleaned_data.get("admin_reply_field")
        
        if reply_text:
            new_message = {"role": "admin", "text": reply_text, "time": timezone.now().strftime("%H:%M")}

            history = list(obj.chat_history) if obj.chat_history else []
            history.append(new_message)
            obj.chat_history = history
            
            obj.is_answered = True

        super().save_model(request, obj, form, change)

admin.site.register(Application, ApplicationAdmin)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("application", "is_from_admin", "created_at")
    list_filter = ("is_from_admin", "created_at")
    search_fields = ("application__subject", "application__username", "text")