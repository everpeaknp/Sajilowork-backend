# Development utilities

Run these from the `backend/` directory (not from inside this folder).

| Script | Purpose |
|--------|---------|
| `setup_smtp.py` | Create SMTP config from Django settings |
| `send_test_email.py` | Send a test email via configured SMTP |
| `test_jazzmin.py` | Jazzmin admin diagnostic |
| `test_contact_model.py` | Contact submission model checks |
| `test_contact_save.py` | Contact form save flow test |
| `check_migration_status.py` | Inspect mails/users migrations (SQLite) |
| `check_fk_constraint.py` | Verify contact submission FK |
| `check_contact_columns.py` | Inspect contact table columns |
| `check_tables.py` | List database tables |
| `check_table_ref.py` | Inspect table references |
| `check_users_table.py` | Inspect users table |
| `check_user_table.py` | Legacy users table check |
| `list_tables.py` | List all tables |
| `fix_contact_table.py` | One-off contact table repair |

```bash
python scripts/dev/setup_smtp.py
python scripts/dev/send_test_email.py
```
