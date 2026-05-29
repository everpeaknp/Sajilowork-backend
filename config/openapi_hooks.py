"""drf-spectacular preprocessing and postprocessing hooks."""

from config.openapi import API_TAGS, build_tag_alias_map


def preprocess_exclude_admin(endpoints, **kwargs):
    """Keep only /api/ routes in the published schema."""
    return [
        (path, path_regex, method, callback)
        for path, path_regex, method, callback in endpoints
        # drf-spectacular may provide `path_regex` with or without a leading slash
        # depending on Django/URLResolver version. Accept both so we don't
        # accidentally filter out *all* API endpoints (resulting in `paths: {}`).
        if str(path_regex).startswith('/api/') or str(path_regex).startswith('api/')
    ]


def postprocess_normalize_tags(result, generator, request, public):
    """
    Merge auto-generated lowercase URL tags (e.g. `analytics`) with canonical
  tags from API_TAGS (e.g. `Analytics`) so Swagger UI does not list duplicates.
    """
    alias_map = build_tag_alias_map()
    canonical_by_name = {tag['name']: tag for tag in API_TAGS}

    def _normalize_tag(raw: str) -> str:
        return alias_map.get(str(raw).lower(), raw)

    paths = result.get('paths', {}) or {}
    used_canonical: set[str] = set()

    for path_item in paths.values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict) or 'tags' not in operation:
                continue
            normalized: list[str] = []
            for raw_tag in operation['tags']:
                canonical = _normalize_tag(raw_tag)
                if canonical not in normalized:
                    normalized.append(canonical)
                used_canonical.add(canonical)
            operation['tags'] = normalized

    # Only publish tag metadata for groups that have at least one operation.
    result['tags'] = [
        canonical_by_name[name]
        for name in sorted(used_canonical, key=str.lower)
        if name in canonical_by_name
    ]
    return result
