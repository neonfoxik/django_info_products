# Generated manually to fix hosting issue

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0013_delete_instruction'),
    ]

    operations = [
        migrations.RunSQL(
            "DROP TABLE IF EXISTS bot_instruction;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ] 