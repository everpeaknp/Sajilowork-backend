"""drf-spectacular preprocessing hooks."""


def preprocess_exclude_admin(endpoints, **kwargs):
    """Keep only /api/ routes in the published schema."""
    return [
        (path, path_regex, method, callback)
        for path, path_regex, method, callback in endpoints
        if path_regex.startswith('/api/')
    ]
