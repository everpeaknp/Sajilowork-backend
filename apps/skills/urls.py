from django.urls import path

from .views import SkillViewSet

app_name = 'skills'

urlpatterns = [
    path(
        '',
        SkillViewSet.as_view({'get': 'list', 'post': 'create'}),
        name='skill-list',
    ),
    path(
        '<slug:slug>/',
        SkillViewSet.as_view({'get': 'retrieve'}),
        name='skill-detail',
    ),
]
