from django.db import migrations


SERVICES_FAQ = [
    (
        'What methods of payments are supported?',
        'We support secure platform payments including wallet balance and supported local payment methods. '
        'Funds are held until you approve the delivered work.',
        1,
    ),
    (
        'Can I cancel at anytime?',
        'You may cancel before work begins without a fee. After an order is in progress, cancellation terms '
        'depend on how much work has been completed. Contact the seller or support if you need help resolving a cancellation.',
        2,
    ),
    (
        'How do I get a receipt for my purchase?',
        'A receipt is emailed to you after payment is confirmed. You can also download invoices from your '
        'dashboard under Payments or Order history at any time.',
        3,
    ),
    (
        'Which license do I need?',
        'Standard packages include commercial use for one project. If you need extended rights, white-label usage, '
        'or resale, message the seller before ordering so the correct license can be added to your package.',
        4,
    ),
    (
        'How do I get access to a theme I purchased?',
        'Source files and deliverables are shared in the order workspace once the seller completes the work. '
        'You will receive a notification when files are ready to download.',
        5,
    ),
]

GENERAL_FAQ = [
    (
        'How much does it cost to post a task?',
        'Posting a task on Sajilowork is free. You only pay when you accept an offer and funds are held securely until the work is completed to your satisfaction.',
        1,
    ),
    (
        'How do I choose the right Tasker?',
        'Compare offers by price, availability, and profile details. Read ratings and reviews from other customers before assigning someone to your task.',
        2,
    ),
    (
        'When is payment taken?',
        'Payment is secured when you accept an offer. Funds are held in escrow and released to the Tasker after you approve the completed work, similar to trusted marketplace models.',
        3,
    ),
    (
        'What if I need to cancel a task?',
        'Either party may cancel depending on task status. Fees may apply after an offer is accepted. See our cancellation policy for full details.',
        4,
    ),
    (
        'How do Taskers get paid?',
        'After the poster approves completion, payment is released to the Tasker through the platform wallet and supported payout methods.',
        5,
    ),
    (
        'Is my personal information safe?',
        'We use verification, secure payments, and platform messaging to reduce risk. Read our Privacy Policy for how we handle your data.',
        6,
    ),
    (
        'Can I communicate off the platform?',
        'We recommend keeping all task communication on Sajilowork so support can help if there is a dispute or payment issue.',
        7,
    ),
    (
        'How do I contact support?',
        'Use the Contact Us page to email our team. Include your account email and task ID for faster help.',
        8,
    ),
]


def seed_faq(apps, schema_editor):
    FaqItem = apps.get_model('faq', 'FaqItem')
    for question, answer, sort_order in SERVICES_FAQ:
        FaqItem.objects.get_or_create(
            question=question,
            defaults={
                'answer': answer,
                'category': 'services',
                'sort_order': sort_order,
                'is_published': True,
            },
        )
    for question, answer, sort_order in GENERAL_FAQ:
        FaqItem.objects.get_or_create(
            question=question,
            defaults={
                'answer': answer,
                'category': 'general',
                'sort_order': sort_order,
                'is_published': True,
            },
        )


def unseed_faq(apps, schema_editor):
    FaqItem = apps.get_model('faq', 'FaqItem')
    questions = [item[0] for item in SERVICES_FAQ + GENERAL_FAQ]
    FaqItem.objects.filter(question__in=questions).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('faq', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_faq, unseed_faq),
    ]
