# Imports IfcGUIDs from an excel file to set the approval status in the database
import pandas as pd
import sqlite3

# Define the path to the Excel file containing GUIDs
# Replace with the actual path to your Excel file
csv_file_path = "SuD_Freigabe.xlsx" # Changed file extension to .xlsx

# Define the database file name
db_filename = 'SuD_Datenbank.db'

# Get input for approval type (architect or structure)
approval_type = input("Enter approval type ('architect' or 'structure'): ").lower()

# Validate approval type input
if approval_type not in ['architect', 'structure']:
    print("Invalid approval type. Please enter 'architect' or 'structure'.")
    exit()

# Determine the column to update based on approval type
approval_column = f"approval_{approval_type}"

conn = None

try:
    # Read GUIDs from the Excel file
    try:
        # Assuming the Excel has no header and GUIDs are in the first column (index 0)
        approved_guids_df = pd.read_excel(csv_file_path, header=None) # Changed to read_excel
        approved_guids = approved_guids_df[0].tolist() # Assuming GUIDs are in the first column
        print(f"Read {len(approved_guids)} GUIDs from {csv_file_path}")

    except FileNotFoundError:
        print(f"Error: Excel file not found at {csv_file_path}")
        exit()
    except Exception as e:
        print(f"An error occurred while reading the Excel file: {e}")
        exit()

    # Connect to the SQLite database
    conn = sqlite3.connect(db_filename)
    c = conn.cursor()

    updated_count = 0
    # Iterate through the approved GUIDs and update the database
    for guid in approved_guids:
        # Check if the GUID exists in the database and update the approval status
        # Using a parameterized query to prevent SQL injection
        c.execute(f"UPDATE ifc_objects SET {approval_column} = TRUE WHERE guid = ?", (guid,))
        updated_count += c.rowcount # Check if any row was updated

    # Commit the changes
    conn.commit()

    print(f"Database updated: {updated_count} objects marked as approved for {approval_type}.")

except sqlite3.Error as e:
    print(f"Database error: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")

finally:
    if conn:
        conn.close()