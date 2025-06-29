# Generated by Django 5.1.6 on 2025-06-10 20:42

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0005_aiprompt'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='ai_prompt',
            field=models.ForeignKey(blank=True, help_text='Персональный промпт для этого пользователя. Если не выбран, используется промпт по умолчанию.', null=True, on_delete=django.db.models.deletion.SET_NULL, to='bot.aiprompt', verbose_name='Промпт ИИ'),
        ),
    ]
