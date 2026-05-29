"""
URL routing for Tasks app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TaskViewSet, CategoryViewSet, TaskAttachmentViewSet

app_name = 'tasks'

router = DefaultRouter()
# Register nested resources before the task detail route (lookup by slug),
# otherwise /tasks/categories/ is handled as /tasks/<slug>/ and returns 404.
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'attachments', TaskAttachmentViewSet, basename='attachment')
router.register(r'', TaskViewSet, basename='task')

urlpatterns = [
    path('', include(router.urls)),
]
