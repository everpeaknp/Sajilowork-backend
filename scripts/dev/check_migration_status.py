import sqlite3

conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

# Check django_migrations table
cursor.execute("SELECT app, name, applied FROM django_migrations WHERE app IN ('mails', 'users') ORDER BY app, applied")
migrations = cursor.fetchall()

print("Migrations for mails and users apps:")
print("=" * 80)
for mig in migrations:
    print(f"  {mig[0]}.{mig[1]} - Applied: {mig[2]}")

if not migrations:
    print("  No migrations found!")

# Check if users table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
users_table = cursor.fetchone()
print(f"\nusers table exists: {bool(users_table)}")

# Check if users_user table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users_user'")
users_user_table = cursor.fetchone()
print(f"users_user table exists: {bool(users_user_table)}")

conn.close()
