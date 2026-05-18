from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Application, Message, Profile


@override_settings(STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage")
class IndexRoutingTests(TestCase):
    def setUp(self):
        self.ticket = Application.objects.create(
            user_id=999,
            username="client",
            category="other",
            subject="Test",
            chat_history=[{"role": "user", "text": "hello", "time": "10:00"}],
        )
        self.staff_user = User.objects.create_user(username="admin", password="pass")
        self.staff_user.is_staff = True
        self.staff_user.save(update_fields=["is_staff"])
        self.profile = Profile.objects.create(user=self.staff_user, telegram_id=123456)

    def test_regular_user_gets_default_template(self):
        response = self.client.get(reverse("feedback:feedback_index"), {"user_id": "999"})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "feedback/index.html")

    def test_staff_user_gets_admin_dashboard(self):
        response = self.client.get(reverse("feedback:feedback_index"), {"user_id": "123456"})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "feedback/admin_dashboard.html")
        self.assertIn("tickets", response.context)

    def test_staff_can_load_ticket_chat_partial(self):
        response = self.client.get(
            reverse("feedback:admin_ticket_chat", args=[self.ticket.id]),
            {"user_id": "123456"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "feedback/partials/admin_ticket_chat.html")

    def test_staff_can_reply_from_admin_webapp(self):
        response = self.client.post(
            reverse("feedback:admin_reply_ticket", args=[self.ticket.id]),
            {"user_id": "123456", "reply_text": "Admin javob"},
        )

        self.assertEqual(response.status_code, 200)
        self.ticket.refresh_from_db()

        self.assertTrue(self.ticket.is_answered)
        self.assertEqual(Message.objects.filter(application=self.ticket, is_from_admin=True).count(), 1)
        self.assertIn("Admin javob", [m["text"] for m in self.ticket.chat_history])

    def test_non_staff_is_blocked_from_admin_endpoints(self):
        response = self.client.get(
            reverse("feedback:admin_ticket_chat", args=[self.ticket.id]),
            {"user_id": "999"},
        )
        self.assertEqual(response.status_code, 403)
    