from django.core.management.base import BaseCommand
from bot.cron import check_support_notifications


class Command(BaseCommand):
    help = 'Проверяет необработанные обращения и отправляет уведомления'

    def handle(self, *args, **options):
        result = check_support_notifications()
        self.stdout.write(self.style.SUCCESS(result))
