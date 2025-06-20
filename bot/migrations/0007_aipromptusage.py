# Generated by Django 5.1.6 on 2025-06-10 20:44

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0006_user_ai_prompt'),
    ]

    operations = [
        migrations.CreateModel(
            name='AIPromptUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('used_at', models.DateTimeField(auto_now_add=True, verbose_name='Время использования')),
                ('message_text', models.TextField(blank=True, null=True, verbose_name='Текст сообщения пользователя')),
                ('response_text', models.TextField(blank=True, null=True, verbose_name='Ответ ИИ')),
                ('prompt', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='bot.aiprompt', verbose_name='Промпт')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='bot.user', verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Использование промпта ИИ',
                'verbose_name_plural': 'Использования промптов ИИ',
                'ordering': ['-used_at'],
            },
        ),
    ]
