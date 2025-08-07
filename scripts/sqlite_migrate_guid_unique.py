import sqlite3
import shutil
import os

# Path to your database file
DB_PATH = "ifc_database.db"
BACKUP_PATH = "ifc_database_backup_before_guid_unique.db"

# Backup the original database
if os.path.exists(DB_PATH):
    shutil.copy(DB_PATH, BACKUP_PATH)
    print(f"Backup created: {BACKUP_PATH}")
else:
    print(f"Database file not found: {DB_PATH}")
    exit(1)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()


# 1. Rename old table (handle if already migrated or missing)
try:
    cursor.execute("ALTER TABLE ifc_objects RENAME TO ifc_objects_old")
except sqlite3.OperationalError as e:
    if "no such table" in str(e):
        print("No ifc_objects table found. Nothing to migrate.")
        conn.close()
        exit(0)
    elif "already exists" in str(e):
        print("Migration already applied. Exiting.")
        conn.close()
        exit(0)
    else:
        raise


# 2. Create new table with renamed and reordered columns and UNIQUE constraint
cursor.execute('''CREATE TABLE ifc_objects (
    IfcGuid TEXT UNIQUE,
    Filename TEXT,
    BuildingStorey TEXT,
    Status TEXT DEFAULT 'active',
    ArchitectApproval BOOLEAN DEFAULT FALSE,
    StructuralApproval BOOLEAN DEFAULT FALSE,
    added_date TEXT,
    deleted_date TEXT
)''')

# 3. Copy data, mapping and reordering columns, ignoring duplicates
cursor.execute('''
    INSERT OR IGNORE INTO ifc_objects (IfcGuid, Filename, BuildingStorey, Status, ArchitectApproval, StructuralApproval, added_date, deleted_date)
    SELECT guid, filename, BuildingStorey, status, approval_architect, approval_structure, added_timestamp, deletion_date FROM ifc_objects_old
''')

# 4. Drop old table
cursor.execute("DROP TABLE ifc_objects_old")

conn.commit()
conn.close()
print("Migration complete. The guid column is now UNIQUE.")
