import sqlite3

conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

# Check django_migrations table
cursor.execute("SELECT app, name, applied FROM django_migrations WHERE app='mails' ORDER BY applied")
migrations = cursor.fetchall()

print("Mails app migrations:")
print("=" * 80)
for mig in migrations:
    print(f"  {mig[0]}.{mig[1]} - Applied: {mig[2]}")

if not migrations:
    print("  No migrations found for mails app!")

conn.close()
