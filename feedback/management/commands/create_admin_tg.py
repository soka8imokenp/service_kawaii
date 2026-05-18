from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from feedback.models import Profile


class Command(BaseCommand):
    help = (
        "Create or update a Django admin account and bind it to a Telegram ID. "
        "Supports multiple admins."
    )

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True, help="Django username / admin nickname")
        parser.add_argument("--telegram-id", required=True, type=int, help="Telegram numeric user ID")
        parser.add_argument("--password", required=False, help="Password for the admin account")
        parser.add_argument(
            "--owner",
            action="store_true",
            help="Grant superuser rights (main admin). Without this flag user becomes staff admin.",
        )

    def handle(self, *args, **options):
        username = options["username"].strip()
        telegram_id = options["telegram_id"]
        password = options.get("password")
        is_owner = options["owner"]

        if not username:
            raise CommandError("Username cannot be empty")

        User = get_user_model()

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": f"{username}@example.com",
            },
        )

        if created:
            if not password:
                raise CommandError("For a new user, provide --password")
            user.set_password(password)

        if password:
            user.set_password(password)

        user.is_staff = True
        user.is_superuser = is_owner
        user.save()

        existing_profile = Profile.objects.filter(telegram_id=telegram_id).exclude(user=user).first()
        if existing_profile:
            raise CommandError(
                f"Telegram ID {telegram_id} is already linked to @{existing_profile.user.username}."
            )

        Profile.objects.update_or_create(
            user=user,
            defaults={"telegram_id": telegram_id},
        )

        role = "OWNER (superuser)" if is_owner else "STAFF admin"
        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} @{username} as {role}, telegram_id={telegram_id}"))
