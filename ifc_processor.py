import ifcopenshell
import sqlite3
import tempfile
import os
from typing import Optional, Dict, Any
import logging
from datetime import datetime

class IFCProcessor:
    """Handles IFC file processing and database operations"""
    
    def __init__(self, ifc_file_path: str):
        """Initialize the IFC processor with a file path"""
        self.ifc_file_path = ifc_file_path
        self.ifc_model = None
        self.temp_ifc_path = None
        self._load_ifc_model()
    
    def _load_ifc_model(self):
        """Load the IFC model from file"""
        try:
            self.ifc_model = ifcopenshell.open(self.ifc_file_path)
            logging.info(f"Successfully loaded IFC model from {self.ifc_file_path}")
        except Exception as e:
            logging.error(f"Failed to load IFC model: {str(e)}")
            raise Exception(f"Cannot open IFC file: {str(e)}")
    
    def load_ifc_to_database(self, db_manager, element_type: str = "IfcVirtualElement", original_filename: str = None) -> bool:
        """Extract IFC data and load it into SQLite database using your specific workflow"""
        try:
            if not self.ifc_model:
                return False
            
            # Create the main tracking table based on your schema
            self._create_ifc_objects_table(db_manager)
            
            # Use the original filename if provided, otherwise extract from path
            if original_filename:
                ifc_filename = original_filename
            else:
                ifc_filename = os.path.basename(self.ifc_file_path)
            
            ifc_creation_date = self._extract_creation_date()
            
            # Extract elements of the specified type
            elements = self.ifc_model.by_type(element_type)
            
            if not elements:
                logging.warning(f"No {element_type} found in the IFC file")
                # Still create empty tables for consistency
                return True
            
            # Process the elements using your workflow
            return self._process_elements(elements, ifc_filename, ifc_creation_date, db_manager, element_type)
        
        except Exception as e:
            logging.error(f"Error loading IFC to database: {str(e)}")
            return False
    
    def _create_ifc_objects_table(self, db_manager):
        """Create the ifc_objects table as per your schema"""
        try:
            connection = db_manager.connection
            cursor = connection.cursor()
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS ifc_objects
                             (guid TEXT, filename TEXT, added_timestamp TEXT, status TEXT DEFAULT 'active',
                              approval_architect BOOLEAN DEFAULT FALSE, approval_structure BOOLEAN DEFAULT FALSE,
                              deletion_date TEXT)''')
            connection.commit()
            logging.info("Created ifc_objects table")
        except Exception as e:
            logging.error(f"Error creating ifc_objects table: {str(e)}")
    
    def _extract_creation_date(self) -> Optional[str]:
        """Extract creation date from IFC FILE_NAME header"""
        try:
            ifc_header = self.ifc_model.header
            if ifc_header and hasattr(ifc_header, 'file_name') and hasattr(ifc_header.file_name, 'time_stamp'):
                timestamp_str = str(ifc_header.file_name.time_stamp)
                try:
                    # Parse various datetime formats, handle timezone info
                    datetime_part = timestamp_str.split('+')[0].split('.')[0]
                    timestamp_obj = datetime.strptime(datetime_part, '%Y-%m-%dT%H:%M:%S')
                    creation_date = timestamp_obj.strftime('%y%m%d')
                    logging.info(f"Found creation date in FILE_NAME header: {creation_date}")
                    return creation_date
                except ValueError:
                    logging.warning(f"Could not parse timestamp format from FILE_NAME: {timestamp_str}")
                    return None
            else:
                logging.warning("FILE_NAME header or time_stamp not found")
                return None
        except Exception as e:
            logging.error(f"Error extracting creation date: {str(e)}")
            return None
    
    def _process_elements(self, elements, ifc_filename, ifc_creation_date, db_manager, element_type: str) -> bool:
        """Process IFC elements using your workflow"""
        try:
            connection = db_manager.connection
            cursor = connection.cursor()
            
            # Extract data from elements
            updated_extracted_data = []
            for element in elements:
                updated_extracted_data.append((element.GlobalId, ifc_filename))
            
            # Create set of GUIDs for efficient lookup
            updated_guids = set([item[0] for item in updated_extracted_data])
            
            # Query existing data from database
            existing_data = {}
            cursor.execute("SELECT guid, status FROM ifc_objects WHERE filename = ?", (ifc_filename,))
            for row in cursor.fetchall():
                existing_data[row[0]] = row[1]
            
            logging.info(f"Found {len(existing_data)} existing objects in database for filename '{ifc_filename}'")
            
            # Mark deleted objects
            if existing_data:
                deleted_guids = []
                deletion_timestamp = ifc_creation_date if ifc_creation_date else datetime.now().strftime('%y%m%d')
                
                for guid, status in existing_data.items():
                    if guid not in updated_guids and status == 'active':
                        deleted_guids.append(guid)
                
                if deleted_guids:
                    cursor.executemany('UPDATE ifc_objects SET status = "deleted", deletion_date = ? WHERE guid = ?', 
                                     [(deletion_timestamp, guid) for guid in deleted_guids])
                    logging.info(f"Marked {len(deleted_guids)} objects as 'deleted'")
            
            # Add new objects
            existing_guids_set = set(existing_data.keys())
            new_objects_to_add = []
            added_timestamp = ifc_creation_date if ifc_creation_date else datetime.now().strftime('%y%m%d')
            
            for guid, filename in updated_extracted_data:
                if guid not in existing_guids_set:
                    new_objects_to_add.append((guid, filename, added_timestamp, 'active', False, False, None))
            
            if new_objects_to_add:
                cursor.executemany('INSERT INTO ifc_objects VALUES (?,?,?,?,?,?,?)', new_objects_to_add)
                logging.info(f"Added {len(new_objects_to_add)} new objects to database")
            
            connection.commit()
            return True
            
        except Exception as e:
            logging.error(f"Error processing virtual elements: {str(e)}")
            return False
    
    def _process_entity_group(self, entity_type: str, entities: list, db_manager):
        """Process a group of entities of the same type"""
        try:
            if not entities:
                return
            
            # Extract properties from the first entity to determine table structure
            sample_entity = entities[0]
            columns = self._extract_entity_properties(sample_entity)
            
            # Create table
            db_manager.create_table(entity_type, columns)
            
            # Insert all entities
            rows = []
            for entity in entities:
                row_data = self._entity_to_row(entity, columns)
                if row_data:
                    rows.append(row_data)
            
            if rows:
                db_manager.insert_rows(entity_type, columns, rows)
                logging.info(f"Inserted {len(rows)} rows into {entity_type} table")
        
        except Exception as e:
            logging.error(f"Error processing entity group {entity_type}: {str(e)}")
    
    def _extract_entity_properties(self, entity) -> Dict[str, str]:
        """Extract property names and types from an entity"""
        columns = {
            'GlobalId': 'TEXT PRIMARY KEY',
            'EntityType': 'TEXT',
            'Name': 'TEXT',
            'Description': 'TEXT'
        }
        
        try:
            # Add standard IFC properties
            if hasattr(entity, 'OwnerHistory'):
                columns['OwnerHistory'] = 'TEXT'
            
            # Add entity-specific attributes
            info = entity.get_info()
            for key, value in info.items():
                if key not in columns:
                    if isinstance(value, (int, float)):
                        columns[key] = 'REAL'
                    elif isinstance(value, bool):
                        columns[key] = 'INTEGER'
                    else:
                        columns[key] = 'TEXT'
        
        except Exception as e:
            logging.warning(f"Error extracting properties from entity: {str(e)}")
        
        return columns
    
    def _entity_to_row(self, entity, columns: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """Convert an IFC entity to a database row"""
        try:
            row = {}
            
            # Standard fields
            row['GlobalId'] = getattr(entity, 'GlobalId', str(entity.id()))
            row['EntityType'] = entity.is_a()
            row['Name'] = getattr(entity, 'Name', None)
            row['Description'] = getattr(entity, 'Description', None)
            
            # Additional attributes
            info = entity.get_info()
            for column_name in columns.keys():
                if column_name not in row:
                    value = info.get(column_name)
                    if value is not None:
                        # Convert complex objects to string representation
                        if hasattr(value, 'is_a'):  # IFC entity reference
                            row[column_name] = f"{value.is_a()}({getattr(value, 'GlobalId', str(value.id()))})"
                        elif isinstance(value, (list, tuple)):
                            row[column_name] = str(value)
                        else:
                            row[column_name] = value
                    else:
                        row[column_name] = None
            
            return row
        
        except Exception as e:
            logging.error(f"Error converting entity to row: {str(e)}")
            return None
    
    def update_ifc_from_database(self, db_manager) -> bool:
        """Update the IFC model with data from the database"""
        try:
            if not self.ifc_model:
                return False
            
            tables = db_manager.get_tables()
            
            for table_name in tables:
                self._update_entities_from_table(table_name, db_manager)
            
            return True
        
        except Exception as e:
            logging.error(f"Error updating IFC from database: {str(e)}")
            return False
    
    def _update_entities_from_table(self, table_name: str, db_manager):
        """Update entities of a specific type from database table"""
        try:
            df = db_manager.get_table_data(table_name)
            
            if df.empty:
                return
            
            for _, row in df.iterrows():
                global_id = row.get('GlobalId')
                if not global_id:
                    continue
                
                # Find the entity in the IFC model
                try:
                    entities = self.ifc_model.by_guid(global_id)
                    if not entities:
                        # Try to find by ID if GUID lookup fails
                        continue
                    
                    entity = entities if not isinstance(entities, list) else entities[0]
                    
                    # Update entity properties
                    for column, value in row.items():
                        if column in ['GlobalId', 'EntityType'] or value is None:
                            continue
                        
                        try:
                            if hasattr(entity, column):
                                # Only update simple attribute types
                                if isinstance(value, (str, int, float, bool)):
                                    setattr(entity, column, value)
                        except Exception as attr_error:
                            logging.warning(f"Could not update attribute {column}: {str(attr_error)}")
                
                except Exception as entity_error:
                    logging.warning(f"Could not find/update entity {global_id}: {str(entity_error)}")
                    continue
        
        except Exception as e:
            logging.error(f"Error updating entities from table {table_name}: {str(e)}")
    
    def get_ifc_content(self) -> Optional[bytes]:
        """Get the current IFC model content as bytes"""
        try:
            if not self.ifc_model:
                return None
            
            # Create a temporary file to write the IFC content
            with tempfile.NamedTemporaryFile(delete=False, suffix=".ifc") as tmp_file:
                self.temp_ifc_path = tmp_file.name
            
            # Write the model to the temporary file
            self.ifc_model.write(self.temp_ifc_path)
            
            # Read the content
            with open(self.temp_ifc_path, 'rb') as f:
                content = f.read()
            
            # Clean up
            os.unlink(self.temp_ifc_path)
            
            return content
        
        except Exception as e:
            logging.error(f"Error getting IFC content: {str(e)}")
            return None
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get basic information about the IFC model"""
        try:
            if not self.ifc_model:
                return {}
            
            info = {
                'schema': self.ifc_model.schema,
                'total_entities': len(list(self.ifc_model)),
                'entity_types': {}
            }
            
            # Count entities by type
            for entity in self.ifc_model:
                entity_type = entity.is_a()
                info['entity_types'][entity_type] = info['entity_types'].get(entity_type, 0) + 1
            
            return info
        
        except Exception as e:
            logging.error(f"Error getting model info: {str(e)}")
            return {}
    
    def set_database_file(self, db_manager, db_file_path: str):
        """Switch the database manager to use a new database file."""
        try:
            if db_manager.connection:
                db_manager.connection.close()
            db_manager.connection = sqlite3.connect(db_file_path)
            logging.info(f"Database switched to {db_file_path}")
        except Exception as e:
            logging.error(f"Error switching database file: {str(e)}")
            raise
