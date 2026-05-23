import json
from django.test import TestCase
from django.urls import reverse
from .models import Profile


class SumireApiTests(TestCase):
    def setUp(self):
        self.profile = Profile.objects.create(telegram_id=123456789)

    def test_send_message_requires_post(self):
        url = reverse("feedback:api_send_message")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    def test_send_message_empty_text(self):
        url = reverse("feedback:api_send_message")
        response = self.client.post(
            url,
            data=json.dumps({"text": "", "user_id": 123456789}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("Iltimos, matn kiriting", data["text"])

    def test_send_message_cyrillic_warning(self):
        url = reverse("feedback:api_send_message")
        response = self.client.post(
            url,
            data=json.dumps({"text": "Привет", "user_id": 123456789}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("Faqat lotin yozuvida yozing", data["text"])
        self.assertEqual(data["emotion"], "face palm")

    def test_send_message_greeting(self):
        url = reverse("feedback:api_send_message")
        response = self.client.post(
            url,
            data=json.dumps({"text": "Salom", "user_id": 123456789}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("Salom", data["text"])
        self.assertEqual(data["emotion"], "talking")

    def test_send_message_thanks(self):
        url = reverse("feedback:api_send_message")
        response = self.client.post(
            url,
            data=json.dumps({"text": "Rahmat", "user_id": 123456789}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("Arzimaydi", data["text"])
        self.assertEqual(data["emotion"], "ty")