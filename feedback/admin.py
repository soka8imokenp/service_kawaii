from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .models import Application

# --- CUSTOM BRANDING ---
admin.site.site_header = "🌸 Sumire Control Panel"
admin.site.site_title = "Sumire Service"
admin.site.index_title = "Sumire Boshqaruv Markazi"


class ApplicationAdminForm(forms.ModelForm):
    admin_reply_field = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "style": "width: 100%; border: 1.5px solid #cbd5e1; border-radius: 10px; padding: 12px; font-family: sans-serif; font-size: 14px; box-sizing: border-box; transition: all 0.2s;",
                "placeholder": "Mijozga xabar yozing... (Saqlash bosilganda Telegram orqali ham yuboriladi)",
            }
        ),
        required=False,
        label="Javob matni",
    )

    class Meta:
        model = Application
        fields = ["user_id", "username", "subject"]


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    form = ApplicationAdminForm

    list_display = ("id", "subject", "username", "created_at")
    search_fields = ("id", "username", "subject")
    readonly_fields = ("chat_history_bubbles", "created_at")

    fieldsets = (
        ("📌 Foydalanuvchi ma'lumotlari", {
            "fields": (
                ("user_id", "username"),
                "subject"
            )
        }),
        ("💬 Muloqot va javob yozish", {
            "fields": ("chat_history_bubbles", "admin_reply_field"),
            "description": "Yozilgan xabar mijozning Telegram botiga yuboriladi va Mini App chatiga qo'shiladi.",
        }),
    )

    class Media:
        css = {
            'all': ('css/admin.css',)
        }

    def chat_history_bubbles(self, obj):
        if not obj or not obj.chat_history:
            return format_html('<p style="color: #64748b; font-style: italic; padding: 15px; background: #1e293b; border-radius: 10px; border: 1px dashed #475569; display: inline-block;">Suhbat tarixi hali bo\'sh.</p>')
        
        html = ['<div class="sumire-chat-wrapper" style="display: flex; flex-direction: column; gap: 14px; max-width: 650px; padding: 20px; background: #0b0f19; border-radius: 16px; border: 1px solid #1f2937; box-shadow: inset 0 2px 8px rgba(0,0,0,0.5); font-family: system-ui, -apple-system, sans-serif;">']
        for msg in obj.chat_history:
            role = msg.get('role', 'user')
            text = msg.get('text', '')
            time = msg.get('time', '')
            
            if role == 'admin':
                # Admin bubble (sleek gradient purple-pink)
                html.append(f'''
                <div style="align-self: flex-end; max-width: 80%; display: flex; flex-direction: column; align-items: flex-end;">
                    <div style="background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%); color: #ffffff; padding: 12px 16px; border-radius: 18px 18px 2px 18px; box-shadow: 0 4px 12px rgba(219, 39, 119, 0.25); word-wrap: break-word; text-align: left;">
                        <div style="font-weight: 700; font-size: 10px; color: #ffd6e8; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px;">Sumire (Siz)</div>
                        <div style="font-size: 13.5px; line-height: 1.5; white-space: pre-wrap;">{text}</div>
                        <div style="text-align: right; font-size: 9px; color: #ffd6e8; margin-top: 6px; font-weight: 500;">{time}</div>
                    </div>
                </div>
                ''')
            else:
                # User bubble (slate-grey)
                html.append(f'''
                <div style="align-self: flex-start; max-width: 80%; display: flex; flex-direction: column; align-items: flex-start;">
                    <div style="background: #1e293b; color: #f8fafc; padding: 12px 16px; border-radius: 18px 18px 18px 2px; box-shadow: 0 4px 10px rgba(0,0,0,0.3); border: 1px solid #334155; word-wrap: break-word; text-align: left;">
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
            from django.utils import timezone
            new_message = {"role": "admin", "text": reply_text, "time": timezone.localtime().strftime("%H:%M")}

            history = list(obj.chat_history) if obj.chat_history else []
            history.append(new_message)
            obj.chat_history = history
            
            obj.is_answered = True

            # Also duplicate to Message table (DB integrity)
            from .models import Message
            Message.objects.create(
                application=obj,
                text=reply_text,
                is_from_admin=True
            )

        super().save_model(request, obj, form, change)