"""Service listings — proxy over Task rows tagged listing:service."""
from django.db import models

from apps.tasks.listing import LISTING_KIND_SERVICE, filter_queryset_by_listing_kind, with_listing_kind
from apps.tasks.models import Task


class ServiceQuerySet(models.QuerySet):
    def services(self):
        return filter_queryset_by_listing_kind(self, LISTING_KIND_SERVICE)


class ServiceManager(models.Manager.from_queryset(ServiceQuerySet)):
    def get_queryset(self):
        return filter_queryset_by_listing_kind(super().get_queryset(), LISTING_KIND_SERVICE)


class Service(Task):
    """
    Marketplace service (gig) listing.

    Stored in the tasks table; distinguished by the listing:service tag.
    """

    objects = ServiceManager()

    class Meta:
        proxy = True
        verbose_name = 'Service'
        verbose_name_plural = 'Services'

    def save(self, *args, **kwargs):
        self.tags = with_listing_kind(self.tags, LISTING_KIND_SERVICE)
        super().save(*args, **kwargs)
