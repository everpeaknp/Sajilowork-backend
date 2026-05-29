"""
Backfill latitude/longitude for tasks that have an address but no coordinates.

Usage:
    python manage.py geocode_tasks                # geocode all eligible tasks
    python manage.py geocode_tasks --dry-run      # show what would be done
    python manage.py geocode_tasks --limit 5      # cap number processed
"""
import time

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.tasks.geocoding import build_query_for_task, geocode_location
from apps.tasks.models import Task


class Command(BaseCommand):
    help = "Backfill latitude/longitude for tasks missing coordinates."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without writing.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of tasks to process this run.",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=1.1,
            help="Seconds to wait between Nominatim requests (default 1.1).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]
        sleep_seconds = options["sleep"]

        # Eligible: missing coords AND has at least one non-empty location field.
        qs = (
            Task.objects.filter(
                Q(latitude__isnull=True) | Q(longitude__isnull=True)
            )
            .exclude(
                # Need at least one of: address, city.
                Q(address="") & Q(city=""),
            )
            .exclude(location_type="remote")
            .order_by("-created_at")
        )
        if limit:
            qs = qs[:limit]

        total = qs.count() if limit is None else len(list(qs))
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Found {total} task(s) eligible for geocoding "
                f"(dry_run={dry_run})"
            )
        )

        updated = 0
        skipped = 0
        for task in qs:
            query = build_query_for_task(task)
            self.stdout.write(f"  - {task.slug!r:40s} <- {query!r}")

            if dry_run:
                continue

            result = geocode_location(query)
            if not result:
                self.stdout.write(self.style.WARNING("      no result"))
                skipped += 1
                time.sleep(sleep_seconds)
                continue

            lat, lng = result
            task.latitude = lat
            task.longitude = lng
            task.save(update_fields=["latitude", "longitude"])
            updated += 1
            self.stdout.write(self.style.SUCCESS(f"      -> {lat}, {lng}"))
            time.sleep(sleep_seconds)

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Updated={updated} Skipped={skipped} DryRun={dry_run}"
            )
        )
