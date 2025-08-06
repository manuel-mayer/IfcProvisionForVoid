import ifcopenshell
import sqlite3
import tempfile
import os
from typing import Optional, Dict, Any
import logging

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
    
    def load_ifc_to_database(self, db_manager) -> bool:
        """Extract IFC data and load it into SQLite database"""
        try:
            if not self.ifc_model:
                return False
            
            # Get all entities in the IFC file
            all_entities = self.ifc_model.by_type("IfcRoot")
            
            if not all_entities:
                logging.warning("No IfcRoot entities found in the IFC file")
                return False
            
            # Group entities by type
            entity_groups = {}
            for entity in all_entities:
                entity_type = entity.is_a()
                if entity_type not in entity_groups:
                    entity_groups[entity_type] = []
                entity_groups[entity_type].append(entity)
            
            # Process each entity type
            for entity_type, entities in entity_groups.items():
                self._process_entity_group(entity_type, entities, db_manager)
            
            return True
        
        except Exception as e:
            logging.error(f"Error loading IFC to database: {str(e)}")
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
