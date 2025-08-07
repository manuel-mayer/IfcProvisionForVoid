# Adds a new column to the 'ifc_objects' table in the SQLite database file.
import sqlite3

# Path to your database file
DB_PATH = "ifc_database.db"  # Change this if your DB is elsewhere

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE ifc_objects ADD COLUMN BuildingStorey TEXT;")
    print("Column 'BuildingStorey' added.")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("Column 'BuildingStorey' already exists.")
    else:
        print("Error:", e)

conn.commit()
conn.close()
