"""Lightweight health check for load balancers and container orchestration."""
from django.db import connection
from django.http import JsonResponse


def health_check(request):
    """GET /health/ — returns 200 when the app and database are reachable."""
    db_ok = True
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    except Exception:
        db_ok = False

    status = 200 if db_ok else 503
    return JsonResponse(
        {
            'status': 'ok' if db_ok else 'degraded',
            'database': 'ok' if db_ok else 'unavailable',
        },
        status=status,
    )
