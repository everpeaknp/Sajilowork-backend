import sqlite3

conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%contact%'")
tables = cursor.fetchall()

print("Tables with 'contact' in name:")
for table in tables:
    print(f"  - {table[0]}")

# Check if ContactSubmission table exists with exact name
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='contact_submissions'")
result = cursor.fetchone()

if result:
    print("\n✓ contact_submissions table EXISTS")
else:
    print("\n✗ contact_submissions table DOES NOT EXIST")

# Show all mails_ tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'mails_%'")
mails_tables = cursor.fetchall()

print("\nTables in mails app:")
for table in mails_tables:
    print(f"  - {table[0]}")

conn.close()
