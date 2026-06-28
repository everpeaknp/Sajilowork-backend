import sqlite3

conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()

print("Tables in database:")
print("-" * 50)
for table in tables:
    print(f"  - {table[0]}")
    
print(f"\nTotal tables: {len(tables)}")

# Check specifically for users_user table
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users_user'")
user_table = cursor.fetchone()
if user_table:
    print("\n✓ users_user table EXISTS")
else:
    print("\n✗ users_user table DOES NOT EXIST")

conn.close()
