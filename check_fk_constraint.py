import sqlite3

conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

# Get the schema for contact_submissions table
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='contact_submissions'")
schema = cursor.fetchone()

print("contact_submissions table schema:")
print("=" * 80)
if schema:
    print(schema[0])
else:
    print("Table does not exist")

# Check foreign key constraints
print("\n\nForeign Key Constraints:")
print("=" * 80)
cursor.execute("PRAGMA foreign_key_list(contact_submissions)")
fk_constraints = cursor.fetchall()
for fk in fk_constraints:
    print(f"  Column: {fk[3]}")
    print(f"  References table: {fk[2]}")
    print(f"  References column: {fk[4]}")
    print()

conn.close()
