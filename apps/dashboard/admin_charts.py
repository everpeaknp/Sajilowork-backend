"""Chart payload helpers for admin report dashboards."""

REPORT_PERIOD_CHOICES = (
    (7, '7 days'),
    (30, '30 days'),
    (90, '90 days'),
    (365, '1 year'),
    (0, 'All time'),
)


def parse_report_period(request, default: int = 30) -> tuple[int | None, int, str]:
    """Return (period_days or None for all time, raw days int, label)."""
    raw = request.GET.get('days', str(default))
    try:
        days = int(raw)
    except (TypeError, ValueError):
        days = default
    if days == 0:
        return None, 0, 'All time'
    return days, days, f'Last {days} days'


def _title(s: str) -> str:
    return (s or 'unknown').replace('_', ' ').title()


def rows_to_chart(rows, label_key: str, value_key: str = 'total', *, count_key: str | None = None):
    """Build Chart.js labels/values from queryset .values() rows."""
    labels = []
    values = []
    for row in rows:
        raw = row.get(label_key)
        labels.append(_title(str(raw)) if raw is not None else 'Unknown')
        if count_key and value_key not in row:
            values.append(float(row.get(count_key) or 0))
        else:
            values.append(float(row.get(value_key) or row.get('count') or 0))
    return {'labels': labels, 'values': values}


def daily_series(queryset_rows, day_key='day', value_key='count'):
    labels = []
    values = []
    for row in queryset_rows:
        day = row.get(day_key)
        labels.append(day.strftime('%d %b') if day else '')
        values.append(float(row.get(value_key) or 0))
    return {'labels': labels, 'values': values}
