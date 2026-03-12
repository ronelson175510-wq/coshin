import mysql.connector

# Database connection
conn = mysql.connector.connect(
    host='localhost',
    user='root',
    password='47406092Jm@',
    database='zimcom'
)

cursor = conn.cursor()

print("🗑️  Starting database cleanup...\n")

# List of tables to clear (in order to respect foreign key constraints)
tables_to_clear = [
    'likes',
    'comments',
    'subscriptions',
    'messages',
    'reels',
    'videos',
    'photos',
    'posts',
    'products',
    'users'
]

# Count records before deletion
print("📊 Current database state:")
for table in tables_to_clear:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"   {table}: {count} records")

print("\n⚠️  WARNING: This will delete ALL data from the database!")
print("Tables to be cleared:", ', '.join(tables_to_clear))
print("\nPress Ctrl+C to cancel, or wait 3 seconds to continue...")

import time
time.sleep(3)

print("\n🔥 Deleting all records...\n")

# Delete all records from each table
for table in tables_to_clear:
    try:
        cursor.execute(f"DELETE FROM {table}")
        rows_deleted = cursor.rowcount
        print(f"✓ Cleared {table}: {rows_deleted} records deleted")
    except Exception as e:
        print(f"✗ Error clearing {table}: {e}")

# Reset auto-increment counters to start fresh
print("\n🔄 Resetting auto-increment counters...\n")
for table in tables_to_clear:
    try:
        cursor.execute(f"ALTER TABLE {table} AUTO_INCREMENT = 1")
        print(f"✓ Reset {table} ID counter")
    except Exception as e:
        print(f"✗ Error resetting {table}: {e}")

# Commit all changes
conn.commit()

print("\n✅ Database cleanup complete!")
print("\n📋 Final database state:")
for table in tables_to_clear:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"   {table}: {count} records")

cursor.close()
conn.close()

print("\n🎉 Database is now clean and ready for fresh data!")
print("💡 All new signups, posts, photos, and videos will be stored in the database.")
print("📱 Users can now log in from any device and see their data.")
