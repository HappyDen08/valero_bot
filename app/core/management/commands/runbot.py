import asyncio

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Запускає Telegram-бота (aiogram, long polling)"

    def handle(self, *args, **options):
        from bot.main import run_bot

        asyncio.run(run_bot())
