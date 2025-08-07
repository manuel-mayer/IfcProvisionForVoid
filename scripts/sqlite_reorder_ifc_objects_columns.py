# reorders columnns in the sqlite file
import sqlite3

DB_PATH = "../ifc_database.db"  # Adjust path if needed

# New column order: guid, filename, BuildingStorey, added_timestamp, status, approval_architect, approval_structure, deletion_date
NEW_COLUMNS = [
    "guid", "filename", "BuildingStorey", "added_timestamp", "status", "approval_architect", "approval_structure", "deletion_date"
]

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 1. Create new table with correct column order
cursor.execute('''CREATE TABLE IF NOT EXISTS ifc_objects_new (
    guid TEXT,
    filename TEXT,
    BuildingStorey TEXT,
    added_timestamp TEXT,
    status TEXT DEFAULT 'active',
    approval_architect BOOLEAN DEFAULT FALSE,
    approval_structure BOOLEAN DEFAULT FALSE,
    deletion_date TEXT
)''')

# 2. Copy data from old table to new table, mapping columns
# Get the columns in the current table
cursor.execute('PRAGMA table_info(ifc_objects)')
old_columns = [row[1] for row in cursor.fetchall()]

# Build SELECT statement to match new order, using NULL if missing
select_expr = ', '.join([
    col if col in old_columns else 'NULL as ' + col for col in NEW_COLUMNS
])

cursor.execute(f'INSERT INTO ifc_objects_new ({', '.join(NEW_COLUMNS)}) SELECT {select_expr} FROM ifc_objects')

# 3. Drop old table and rename new table
cursor.execute('DROP TABLE ifc_objects')
cursor.execute('ALTER TABLE ifc_objects_new RENAME TO ifc_objects')

conn.commit()
conn.close()
print("ifc_objects table reordered: BuildingStorey is now after filename.")
