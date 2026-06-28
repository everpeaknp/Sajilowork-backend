"""Check for users table"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'db.sqlite3')

print(f"Connecting to database: {DB_PATH}")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# List all tables
print("\nAll tables in database:")
print("-" * 80)
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()
for table in tables:
    print(f"  - {table[0]}")

# Check for user-related tables
print("\nTables with 'user' in name:")
print("-" * 80)
user_tables = [t[0] for t in tables if 'user' in t[0].lower()]
for table in user_tables:
    print(f"  - {table}")

conn.close()
