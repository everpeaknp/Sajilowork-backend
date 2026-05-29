from django.db import migrations


DEFAULT_LIMIT_POLICIES = [
    (
        "OFFER",
        "task_budget_limits",
        "Task budget limits",
        ["task.created"],
        {
            "min_budget_npr": "100",
            "max_budget_npr": "100000",
        },
    ),
    (
        "WALLET",
        "recharge_amount_limits",
        "Wallet recharge limits",
        [],
        {
            "min_recharge_amount": 100,
            "max_recharge_amount": 10000,
        },
    ),
    (
        "WITHDRAWAL",
        "withdrawal_amount_limits",
        "Withdrawal amount limits",
        ["withdrawal.requested"],
        {
            "min_withdrawal_amount_npr": "10",
            "max_withdrawal_amount_npr": "50000",
        },
    ),
]


def seed_limit_policies(apps, schema_editor):
    RulePolicy = apps.get_model("rules", "RulePolicy")
    for category, slug, name, triggers, params in DEFAULT_LIMIT_POLICIES:
        RulePolicy.objects.get_or_create(
            category=category,
            slug=slug,
            defaults={
                "name": name,
                "description": name,
                "is_active": True,
                "priority": 100,
                "enforcement": "BLOCK",
                "event_triggers": triggers,
                "conditions": {},
                "parameters": params,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("rules", "0002_rule_engine_policies"),
    ]

    operations = [
        migrations.RunPython(seed_limit_policies, migrations.RunPython.noop),
    ]

