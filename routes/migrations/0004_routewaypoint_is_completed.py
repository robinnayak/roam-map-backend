from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("routes", "0003_userroute_routewaypoint"),
    ]

    operations = [
        migrations.AddField(
            model_name="routewaypoint",
            name="is_completed",
            field=models.BooleanField(default=False),
        ),
    ]
