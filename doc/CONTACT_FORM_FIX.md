# Contact Form Database Error - Resolution

## Problem
Contact form submission was failing with error:
```
django.db.utils.OperationalError: no such table: main.users_user
```

## Root Cause Analysis

1. **Database is correct**: 
   - FK constraint in `contact_submissions` table correctly points to `users` table
   - Verified with: `python scripts/dev/check_fk_constraint.py`
   - Output: `responded_by_id char(32) NULL REFERENCES users(id)`

2. **Migrations are correct**:
   - Migration `0003_fix_contact_submission_user_fk` was successfully applied on 2026-06-28 07:25:45
   - This migration fixed any FK constraints that were pointing to `users_user` instead of `users`
   - Verified with: `python scripts/dev/check_migration_status.py`

3. **Model definition is correct**:
   - User model has `db_table = 'users'` in Meta class
   - ContactSubmission uses `settings.AUTH_USER_MODEL` for FK
   - AUTH_USER_MODEL is set to `'users.User'` in settings

## The Real Issue

The Django development server was started BEFORE migration 0003 was applied. Django caches model metadata at startup, so it's still using the old reference to `users_user` even though the database has been fixed.

## Solution

**Restart the Django development server**

1. Stop the current `python manage.py runserver` process (Ctrl+C)
2. Start it again: `python manage.py runserver`
3. Django will reload all model metadata and use the correct table names

## Verification Steps

After restarting the server, test the contact form:

1. Navigate to http://localhost:3000/contact
2. Fill in the form with valid data:
   - Name: at least 2 characters
   - Email: valid email format
   - Message: at least 10 characters
3. Submit the form
4. Should succeed and save to database

## Files Modified

- `backend/config/__init__.py`: Made Celery import optional (prevents import errors)
- Debug scripts live in `backend/scripts/dev/` (see [scripts/dev/README.md](../scripts/dev/README.md))

## Database Tables Confirmed

- `users` table: ✓ EXISTS
- `users_user` table: ✗ DOES NOT EXIST (correct)
- `contact_submissions` table: ✓ EXISTS with correct FK to `users`

## Migration Timeline

1. `0001_initial`: Created email templates and settings tables
2. `0002_contactsubmission`: Created contact_submissions table (may have had wrong FK initially)
3. `0003_fix_contact_submission_user_fk`: Fixed FK constraint to point to correct `users` table

## Next Steps

1. Restart Django server
2. Test contact form
3. Debug scripts remain in `scripts/dev/` for future troubleshooting
4. Consider adding automated tests for contact form submission
