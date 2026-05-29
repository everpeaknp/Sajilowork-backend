from django.db import migrations
from django.utils import timezone


SEED_POSTS = [
    {
        'slug': 'spotless-move-out-clean',
        'title': '10 Tips for a spotless move-out clean',
        'category': 'Cleaning',
        'excerpt': (
            'Ensure you get your bond back with our definitive cleaning checklist '
            'for every room in the house.'
        ),
        'image_url': (
            'https://lh3.googleusercontent.com/aida-public/AB6AXuAzhpT3UQ3iGBEXRywify7RcdV-FDQOC1shyKY8Z5_GYfudKrSsninDIsyCEzqxuhMhfu9xALwfqS_3aH_Tdbxo4cDHlsXUvZox4m_DrdSgk7mjpY2El-6ZOH_IsUOtuiNmLHFjm-GjMZwrI1_UM3dSyJ9yrVRnM5JeCqMj8lqVztmt_YiuVkGzwhzqcDsuNitJOJRMjF1CZ67YFGwdXukV8bCKcgqfgGjInd4SbmHWFynaJ0gTrXqk9I4GQKTm92PuqL4gQk7jD79F'
        ),
        'sort_order': 1,
    },
    {
        'slug': 'furniture-assembly-hacks',
        'title': 'Furniture assembly hacks you need',
        'category': 'Assembly',
        'excerpt': (
            "Don't lose your mind over those instructions. Here's how the pros build "
            'flatpack furniture in half the time.'
        ),
        'image_url': (
            'https://lh3.googleusercontent.com/aida-public/AB6AXuBG_9_Wnfdm-bgnPDcP3WZVTu4afJ4LJC10XGA-44mnT-ONrfoAvWfBxlzJr7xKjHk9ugKvkycfyKXiC_T98kpe3O-78xKo3hYKv5DE98IBytqdjRtWvCBt8G_V79rasJ6R4gQvw6Lz5RzBlPcBymr8O2hkYofsSdhWgXtzOvDNsvVGKVjGNhhQ7aTor4XcvrVZBb4a3twJ0o-UdqF75qRn4YxNqmqfMRBnaZ3z98ZoEwdJqVsnRdGJmeNJh-K72rhmy03KgCQdGZZE'
        ),
        'sort_order': 2,
    },
    {
        'slug': 'spring-gardening-plant-now',
        'title': 'Spring gardening: What to plant now',
        'category': 'Gardening',
        'excerpt': (
            'Get your garden ready for summer with our guide to seasonal planting and '
            'easy lawn maintenance tips.'
        ),
        'image_url': (
            'https://lh3.googleusercontent.com/aida-public/AB6AXuApgruoUYzXkp9wcWGN4HrcofskA2J2uTC46kpvL4oloqzGvZF5ymxBHZZ-Q5Zzs7AK3a9n0BXHR73Ky2UYy6ncjasBpPqZHIX8QID9-FA087ADsOJuFpmhtRC0P88G_KpGGrRgNz0lfiRapmO3rMg17gP2llSa5aUJWJ57SzKPA-YK0ICwDwHxxHC9D0JP5BRLJOKEHHN5cKfUotf6BesAKzFj0GxyRuUYuuVelDavta5myogmEYpdo3j6H8xn6vNualTOkOPiJOkM'
        ),
        'sort_order': 3,
    },
]


def seed_posts(apps, schema_editor):
    BlogPost = apps.get_model('blog', 'BlogPost')
    now = timezone.now()
    for row in SEED_POSTS:
        BlogPost.objects.update_or_create(
            slug=row['slug'],
            defaults={
                **row,
                'is_published': True,
                'is_featured': True,
                'published_at': now,
            },
        )


def unseed_posts(apps, schema_editor):
    BlogPost = apps.get_model('blog', 'BlogPost')
    BlogPost.objects.filter(slug__in=[p['slug'] for p in SEED_POSTS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_posts, unseed_posts),
    ]
