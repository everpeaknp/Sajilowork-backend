from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="TaskAlertKeyword",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("keyword", models.CharField(max_length=64)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="task_alert_keywords",
                        to="users.user",
                    ),
                ),
            ],
            options={
                "db_table": "task_alert_keywords",
                "unique_together": {("user", "keyword")},
            },
        ),
        migrations.AddIndex(
            model_name="taskalertkeyword",
            index=models.Index(fields=["user", "is_active"], name="task_alert__user_id_0afc9d_idx"),
        ),
        migrations.AddIndex(
            model_name="taskalertkeyword",
            index=models.Index(fields=["user", "keyword"], name="task_alert__user_id_f5b3b9_idx"),
        ),
    ]

