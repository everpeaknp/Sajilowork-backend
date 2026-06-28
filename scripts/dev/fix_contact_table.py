"""Fix contact_submissions table schema"""
import sqlite3
import os

# Path to database
DB_PATH = os.path.join(os.path.dirname(__file__), 'db.sqlite3')

print(f"Connecting to database: {DB_PATH}")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    # Check current columns
    print("\n1. Current columns in contact_submissions:")
    print("-" * 80)
    cursor.execute("PRAGMA table_info(contact_submissions)")
    columns = cursor.fetchall()
    for col in columns:
        print(f"  {col[1]:20s} {col[2]:15s}")
    
    # Check if admin_response exists
    column_names = [col[1] for col in columns]
    has_admin_response = 'admin_response' in column_names
    has_admin_notes = 'admin_notes' in column_names
    has_responded_by = 'responded_by_id' in column_names
    
    print(f"\nStatus:")
    print(f"  - has admin_response: {has_admin_response}")
    print(f"  - has admin_notes: {has_admin_notes}")
    print(f"  - has responded_by_id: {has_responded_by}")
    
    if has_admin_response and not has_admin_notes:
        print("\n2. Renaming admin_response to admin_notes...")
        cursor.execute("ALTER TABLE contact_submissions RENAME COLUMN admin_response TO admin_notes")
        print("✓ Column renamed successfully")
    elif has_admin_notes:
        print("\n2. admin_notes column already exists")
    
    if not has_responded_by:
        print("\n3. Adding responded_by_id column...")
        cursor.execute("""
            ALTER TABLE contact_submissions 
            ADD COLUMN responded_by_id char(32) NULL 
            REFERENCES users(id)
        """)
        print("✓ Column added successfully")
    else:
        print("\n3. responded_by_id column already exists")
    
    # Fix user_agent if needed
    print("\n4. Checking user_agent column type...")
    user_agent_col = [col for col in columns if col[1] == 'user_agent']
    if user_agent_col:
        print(f"  Current type: {user_agent_col[0][2]}")
        if user_agent_col[0][2] == 'text':
            print("  Note: user_agent is TEXT but model expects VARCHAR(500)")
            print("  This is acceptable - SQLite treats them similarly")
    
    conn.commit()
    print("\n✓ All changes applied successfully")
    
    # Verify final schema
    print("\n5. Final columns in contact_submissions:")
    print("-" * 80)
    cursor.execute("PRAGMA table_info(contact_submissions)")
    columns = cursor.fetchall()
    for col in columns:
        print(f"  {col[1]:20s} {col[2]:15s}")
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    conn.rollback()
finally:
    conn.close()
    print("\nDatabase connection closed.")
