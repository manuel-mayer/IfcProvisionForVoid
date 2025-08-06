import sqlite3
import pandas as pd
import tempfile
import os
from typing import List, Dict, Any, Optional
import logging

class DatabaseManager:
    """Manages SQLite database operations for IFC data"""
    
    def __init__(self):
        """Initialize database manager with in-memory database"""
        self.db_path = ":memory:"
        self.connection = None
        self._connect()
    
    def _connect(self):
        """Establish database connection"""
        try:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row  # Enable column access by name
            logging.info("Database connection established")
        except Exception as e:
            logging.error(f"Failed to connect to database: {str(e)}")
            raise
    
    def create_table(self, table_name: str, columns: Dict[str, str]) -> bool:
        """Create a table with specified columns"""
        try:
            if not self.connection:
                return False
            
            # Sanitize table name
            safe_table_name = self._sanitize_table_name(table_name)
            
            # Build CREATE TABLE statement
            column_definitions = []
            for col_name, col_type in columns.items():
                safe_col_name = self._sanitize_column_name(col_name)
                column_definitions.append(f"{safe_col_name} {col_type}")
            
            create_sql = f"CREATE TABLE IF NOT EXISTS {safe_table_name} ({', '.join(column_definitions)})"
            
            cursor = self.connection.cursor()
            cursor.execute(create_sql)
            self.connection.commit()
            
            logging.info(f"Created table {safe_table_name} with {len(columns)} columns")
            return True
        
        except Exception as e:
            logging.error(f"Error creating table {table_name}: {str(e)}")
            return False
    
    def insert_rows(self, table_name: str, columns: Dict[str, str], rows: List[Dict[str, Any]]) -> bool:
        """Insert multiple rows into a table"""
        try:
            if not self.connection or not rows:
                return False
            
            safe_table_name = self._sanitize_table_name(table_name)
            safe_columns = [self._sanitize_column_name(col) for col in columns.keys()]
            
            # Prepare INSERT statement
            placeholders = ', '.join(['?' for _ in safe_columns])
            insert_sql = f"INSERT OR REPLACE INTO {safe_table_name} ({', '.join(safe_columns)}) VALUES ({placeholders})"
            
            # Prepare row data
            row_data = []
            for row in rows:
                row_values = []
                for col in columns.keys():
                    value = row.get(col)
                    # Handle None values and convert complex types to strings
                    if value is None:
                        row_values.append(None)
                    elif isinstance(value, (list, dict, tuple)):
                        row_values.append(str(value))
                    else:
                        row_values.append(value)
                row_data.append(row_values)
            
            cursor = self.connection.cursor()
            cursor.executemany(insert_sql, row_data)
            self.connection.commit()
            
            logging.info(f"Inserted {len(rows)} rows into {safe_table_name}")
            return True
        
        except Exception as e:
            logging.error(f"Error inserting rows into {table_name}: {str(e)}")
            return False
    
    def get_tables(self) -> List[str]:
        """Get list of all tables in the database"""
        try:
            if not self.connection:
                return []
            
            cursor = self.connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
            
            return tables
        
        except Exception as e:
            logging.error(f"Error getting tables: {str(e)}")
            return []
    
    def get_table_data(self, table_name: str) -> pd.DataFrame:
        """Get all data from a table as a pandas DataFrame"""
        try:
            if not self.connection:
                return pd.DataFrame()
            
            safe_table_name = self._sanitize_table_name(table_name)
            query = f"SELECT * FROM {safe_table_name}"
            
            df = pd.read_sql_query(query, self.connection)
            return df
        
        except Exception as e:
            logging.error(f"Error getting data from table {table_name}: {str(e)}")
            return pd.DataFrame()
    
    def update_table_data(self, table_name: str, df: pd.DataFrame) -> bool:
        """Update table data with DataFrame content"""
        try:
            if not self.connection or df.empty:
                return False
            
            safe_table_name = self._sanitize_table_name(table_name)
            
            # Clear existing data
            cursor = self.connection.cursor()
            cursor.execute(f"DELETE FROM {safe_table_name}")
            
            # Insert updated data
            df.to_sql(safe_table_name, self.connection, if_exists='append', index=False)
            self.connection.commit()
            
            logging.info(f"Updated {len(df)} rows in {safe_table_name}")
            return True
        
        except Exception as e:
            logging.error(f"Error updating table {table_name}: {str(e)}")
            return False
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get information about a table structure"""
        try:
            if not self.connection:
                return {}
            
            safe_table_name = self._sanitize_table_name(table_name)
            cursor = self.connection.cursor()
            cursor.execute(f"PRAGMA table_info({safe_table_name})")
            
            columns = cursor.fetchall()
            info = {
                'columns': [{'name': col[1], 'type': col[2], 'not_null': bool(col[3]), 'primary_key': bool(col[5])} for col in columns],
                'column_count': len(columns)
            }
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {safe_table_name}")
            info['row_count'] = cursor.fetchone()[0]
            
            return info
        
        except Exception as e:
            logging.error(f"Error getting table info for {table_name}: {str(e)}")
            return {}
    
    def get_database_content(self) -> Optional[bytes]:
        """Get the entire database as bytes for download"""
        try:
            if not self.connection:
                return None
            
            # Create a temporary file database
            with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp_file:
                temp_db_path = tmp_file.name
            
            # Copy in-memory database to file
            file_db = sqlite3.connect(temp_db_path)
            self.connection.backup(file_db)
            file_db.close()
            
            # Read the file content
            with open(temp_db_path, 'rb') as f:
                content = f.read()
            
            # Clean up
            os.unlink(temp_db_path)
            
            return content
        
        except Exception as e:
            logging.error(f"Error getting database content: {str(e)}")
            return None
    
    def execute_query(self, query: str) -> pd.DataFrame:
        """Execute a custom SQL query and return results as DataFrame"""
        try:
            if not self.connection:
                return pd.DataFrame()
            
            df = pd.read_sql_query(query, self.connection)
            return df
        
        except Exception as e:
            logging.error(f"Error executing query: {str(e)}")
            return pd.DataFrame()
    
    def _sanitize_table_name(self, table_name: str) -> str:
        """Sanitize table name to prevent SQL injection"""
        # Remove or replace invalid characters
        sanitized = ''.join(c for c in table_name if c.isalnum() or c in '_')
        # Ensure it starts with a letter or underscore
        if sanitized and not (sanitized[0].isalpha() or sanitized[0] == '_'):
            sanitized = f"tbl_{sanitized}"
        return sanitized or "unknown_table"
    
    def _sanitize_column_name(self, column_name: str) -> str:
        """Sanitize column name to prevent SQL injection"""
        # Remove or replace invalid characters
        sanitized = ''.join(c for c in column_name if c.isalnum() or c in '_')
        # Ensure it starts with a letter or underscore
        if sanitized and not (sanitized[0].isalpha() or sanitized[0] == '_'):
            sanitized = f"col_{sanitized}"
        return sanitized or "unknown_column"
    
    def close(self):
        """Close database connection"""
        try:
            if self.connection:
                self.connection.close()
                logging.info("Database connection closed")
        except Exception as e:
            logging.error(f"Error closing database connection: {str(e)}")
    
    def __del__(self):
        """Destructor to ensure connection is closed"""
        self.close()
