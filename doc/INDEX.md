# Backend documentation

Internal notes and reference material. The main setup guide stays in [README.md](../README.md).

## Guides

| Document | Description |
|----------|-------------|
| [CONTACT_FORM_FIX.md](./CONTACT_FORM_FIX.md) | Contact form FK / migration fix notes |
| [CONTACT_FORM_SETUP.md](./CONTACT_FORM_SETUP.md) | Contact form SMTP and API setup |
| [mails-api-reference.md](./mails-api-reference.md) | Mails app API reference |
| [DASHBOARD_SUMMARY.txt](./DASHBOARD_SUMMARY.txt) | Admin dashboard implementation summary |
| [JAZZMIN_SUMMARY.txt](./JAZZMIN_SUMMARY.txt) | Jazzmin admin theme configuration summary |

## API exports

| File | Description |
|------|-------------|
| [api/schema.yml](./api/schema.yml) | OpenAPI schema (YAML) |
| [api/schema.json](./api/schema.json) | OpenAPI schema (JSON) |

## Dev scripts

One-off debugging and setup utilities live in [../scripts/dev/](../scripts/dev/). Run from the `backend/` directory, for example:

```bash
python scripts/dev/setup_smtp.py
python scripts/dev/send_test_email.py
```

Production scripts (`entrypoint.sh`, `deploy.sh`, seed scripts) remain in [../scripts/](../scripts/).
