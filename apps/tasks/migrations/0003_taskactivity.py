# Hand-written migration to create the missing `task_activities` table.
#
# Why this exists:
#   - The `TaskActivity` model (apps.tasks.models.TaskActivity) was added to
#     models.py but no migration was ever generated/applied for it.
#   - Result: any code path that touched `instance.activities.<...>` raised
#     `OperationalError: no such table: task_activities`, including the
#     diagnostic logging in `TaskViewSet.destroy()`. That made it impossible
#     to delete tasks (DELETE /api/v1/tasks/<slug>/ returned HTTP 500).
#   - We avoid running `makemigrations` because the reviews app has unrelated
#     pending model changes that would also be picked up and require human
#     judgement (field renames + a new non-nullable field). Writing this
#     migration by hand keeps the change surface minimal.
#
# Faithful to the model definition at apps/tasks/models.py: TaskActivity.

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0002_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TaskActivity",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "activity_type",
                    models.CharField(
                        choices=[
                            ("created", "Task Created"),
                            ("published", "Task Published"),
                            ("bid_received", "Bid Received"),
                            ("bid_accepted", "Bid Accepted"),
                            ("bid_rejected", "Bid Rejected"),
                            ("assigned", "Task Assigned"),
                            ("started", "Task Started"),
                            ("progress_updated", "Progress Updated"),
                            ("completion_requested", "Completion Requested"),
                            ("revision_requested", "Revision Requested"),
                            ("completed", "Task Completed"),
                            ("approved", "Task Approved"),
                            ("payment_released", "Payment Released"),
                            ("reviewed", "Review Submitted"),
                            ("cancelled", "Task Cancelled"),
                            ("disputed", "Dispute Raised"),
                            ("message_sent", "Message Sent"),
                            ("attachment_uploaded", "Attachment Uploaded"),
                        ],
                        max_length=30,
                    ),
                ),
                ("description", models.TextField()),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="task_activities",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="activities",
                        to="tasks.task",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Task Activities",
                "db_table": "task_activities",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["task", "-created_at"],
                        name="task_activi_task_id_ad7e94_idx",
                    ),
                    models.Index(
                        fields=["activity_type"],
                        name="task_activi_activit_4b34d2_idx",
                    ),
                ],
            },
        ),
    ]
