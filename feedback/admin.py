from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.html import format_html

from .models import Application, Message, Profile

# --- CUSTOM BRANDING ---
admin.site.site_header = "🌸 Sumire Control Panel"
admin.site.site_title = "Sumire Service"
admin.site.index_title = "Sumire Boshqaruv Markazi"


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
            if self.instance and self.instance.pk and hasattr(self.instance, 'user') and self.instance.user:
                profile.user = None

        if commit:
            profile.save()

        return profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    form = ProfileAdminForm
    list_display = ("telegram_id", "admin_username", "admin_role_badge", "favorite_genres")
    search_fields = ("telegram_id", "favorite_genres", "user__username")
    list_filter = ("user__is_superuser", "user__is_staff")
    
    fieldsets = (
        ("📌 Asosiy ma'lumotlar", {"fields": ("telegram_id", "favorite_genres")}),
        ("🔑 Admin huquqlari (Faqat xodimlar uchun)", {"fields": ("username", "password", "is_owner")}),
    )

    class Media:
        css = {
            'all': ('css/admin.css',)
        }

    def admin_username(self, obj):
        if hasattr(obj, 'user') and obj.user:
            return obj.user.username
        return "Mijoz (User)"
    admin_username.short_description = "Foydalanuvchi nomi (Nick)"

    def admin_role_badge(self, obj):
        if hasattr(obj, 'user') and obj.user:
            if obj.user.is_superuser:
                return format_html('<span style="background: linear-gradient(135deg, #a855f7 0%, #ec4899 100%); color: #fff; padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 10px; text-transform: uppercase; box-shadow: 0 2px 4px rgba(236, 72, 153, 0.2);">Owner</span>')
            return format_html('<span style="background: #3b82f6; color: #fff; padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 10px; text-transform: uppercase; box-shadow: 0 2px 4px rgba(59, 130, 246, 0.2);">Admin</span>')
        return format_html('<span style="background: #475569; color: #cbd5e1; padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 10px; text-transform: uppercase;">Mijoz</span>')
    admin_role_badge.short_description = "Rol"


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("created_at",)
    fields = ("text", "is_from_admin", "created_at")
    classes = ('collapse',)


class ApplicationAdminForm(forms.ModelForm):
    admin_reply_field = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "style": "width: 100%; border: 1.5px solid #d1d5db; border-radius: 10px; padding: 12px; font-family: sans-serif; font-size: 14px; box-sizing: border-box; transition: all 0.2s;",
                "placeholder": "Mijozga xabar yozing... (Saqlash bosilganda Telegram orqali ham yuboriladi)",
            }
        ),
        required=False,
        label="Javob matni",
    )

    class Meta:
        model = Application
        fields = "__all__"


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    form = ApplicationAdminForm
    inlines = [MessageInline]

    list_display = ("subject", "username", "category_badge", "status_is_answered", "status_is_closed", "created_at")
    list_filter = ("is_closed", "category", "is_answered")
    readonly_fields = ("chat_history_bubbles", "chat_history", "created_at", "updated_at")

    fieldsets = (
        ("📌 Ariza tafsilotlari", {
            "fields": (
                ("user_id", "username"),
                ("category", "subject"),
                ("is_closed", "is_answered")
            )
        }),
        ("💬 Suhbat va yozishmalar (Vizual)", {
            "fields": ("chat_history_bubbles",),
        }),
        ("✍️ Yangi javob yozish", {
            "fields": ("admin_reply_field",),
            "description": "Bu yerga yozilgan xabar foydalanuvchining Telegramiga yuboriladi va Web App chatiga qo'shiladi.",
        }),
        ("⚙️ Texnik ma'lumotlar (Tizim loglari)", {
            "classes": ("collapse",),
            "fields": ("chat_history", "created_at", "updated_at"),
        }),
    )

    class Media:
        css = {
            'all': ('css/admin.css',)
        }

    def status_is_answered(self, obj):
        if obj.is_answered:
            return format_html('<span style="background: #d1fae5; color: #065f46; border: 1px solid #a7f3d0; padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 11px; text-transform: uppercase; box-shadow: 0 1px 2px rgba(16, 185, 129, 0.15);">Javob berilgan</span>')
        return format_html('<span style="background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 11px; text-transform: uppercase; box-shadow: 0 1px 2px rgba(239, 68, 68, 0.15);">Kutilmoqda</span>')
    status_is_answered.short_description = "Javob holati"

    def status_is_closed(self, obj):
        if obj.is_closed:
            return format_html('<span style="background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 11px; text-transform: uppercase;">Yopilgan</span>')
        return format_html('<span style="background: #dbeafe; color: #1e40af; border: 1px solid #bfdbfe; padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 11px; text-transform: uppercase; box-shadow: 0 1px 2px rgba(59, 130, 246, 0.15);">Faol (Ochiq)</span>')
    status_is_closed.short_description = "Ariza holati"

    def category_badge(self, obj):
        colors = {
            'news': ('#e0f2fe', '#0369a1', '#bae6fd'),   # Blue
            'ads': ('#fef3c7', '#b45309', '#fde68a'),    # Yellow
            'report': ('#ffe4e6', '#be123c', '#fecdd3'), # Red
            'collab': ('#f3e8ff', '#6b21a8', '#e9d5ff'), # Purple
            'other': ('#f1f5f9', '#334155', '#e2e8f0'),  # Grey
        }
        bg, fg, border = colors.get(obj.category, ('#f1f5f9', '#334155', '#e2e8f0'))
        return format_html(f'<span style="background: {bg}; color: {fg}; border: 1px solid {border}; padding: 3px 8px; border-radius: 8px; font-weight: 600; font-size: 11px;">{obj.get_category_display()}</span>')
    category_badge.short_description = "Kategoriya"

    def chat_history_bubbles(self, obj):
        if not obj or not obj.chat_history:
            return format_html('<p style="color: #64748b; font-style: italic; padding: 15px; background: #f8fafc; border-radius: 10px; border: 1px dashed #cbd5e1; display: inline-block;">Suhbat tarixi hali bo\'sh.</p>')
        
        html = ['<div class="sumire-chat-wrapper" style="display: flex; flex-direction: column; gap: 14px; max-width: 650px; padding: 20px; background: #0f172a; border-radius: 16px; border: 1px solid #334155; box-shadow: inset 0 2px 8px rgba(0,0,0,0.4); font-family: system-ui, -apple-system, sans-serif;">']
        for msg in obj.chat_history:
            role = msg.get('role', 'user')
            text = msg.get('text', '')
            time = msg.get('time', '')
            
            if role == 'admin':
                # Admin bubble (right aligned, sleek purple-pink gradient)
                html.append(f'''
                <div style="align-self: flex-end; max-width: 80%; display: flex; flex-direction: column; align-items: flex-end;">
                    <div style="background: linear-gradient(135deg, #a855f7 0%, #ec4899 100%); color: #ffffff; padding: 12px 16px; border-radius: 18px 18px 2px 18px; box-shadow: 0 4px 12px rgba(236, 72, 153, 0.2); word-wrap: break-word; text-align: left;">
                        <div style="font-weight: 700; font-size: 10px; color: #ffd6e8; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px;">Sumire (Siz)</div>
                        <div style="font-size: 13.5px; line-height: 1.5; white-space: pre-wrap;">{text}</div>
                        <div style="text-align: right; font-size: 9px; color: #ffd6e8; margin-top: 6px; font-weight: 500;">{time}</div>
                    </div>
                </div>
                ''')
            else:
                # User bubble (left aligned, slate grey background)
                html.append(f'''
                <div style="align-self: flex-start; max-width: 80%; display: flex; flex-direction: column; align-items: flex-start;">
                    <div style="background: #1e293b; color: #f8fafc; padding: 12px 16px; border-radius: 18px 18px 18px 2px; box-shadow: 0 4px 10px rgba(0,0,0,0.15); border: 1px solid #334155; word-wrap: break-word; text-align: left;">
                        <div style="font-weight: 700; font-size: 10px; color: #38bdf8; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px;">@{obj.username or 'Yashirin'} ({obj.user_id})</div>
                        <div style="font-size: 13.5px; line-height: 1.5; white-space: pre-wrap;">{text}</div>
                        <div style="text-align: right; font-size: 9px; color: #94a3b8; margin-top: 6px; font-weight: 500;">{time}</div>
                    </div>
                </div>
                ''')
        html.append('</div>')
        return format_html('\n'.join(html))
    chat_history_bubbles.short_description = "Suhbat ko'rinishi"

    def save_model(self, request, obj, form, change):
        reply_text = form.cleaned_data.get("admin_reply_field")
        
        if reply_text:
            new_message = {"role": "admin", "text": reply_text, "time": timezone.localtime().strftime("%H:%M")}

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
    
    class Media:
        css = {
            'all': ('css/admin.css',)
        }