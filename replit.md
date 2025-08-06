# IFC File Processor

## Overview

This is a Streamlit-based web application for processing and manipulating IFC (Industry Foundation Classes) building data files. The application allows users to upload IFC files, extract their data into SQLite databases, and perform various operations on the building information models. IFC files are standard format files used in the architecture, engineering, and construction (AEC) industry to exchange building information models between different software applications.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Framework**: Streamlit web framework for rapid prototyping and deployment
- **Layout**: Wide layout configuration with sidebar for file operations
- **State Management**: Session state used to persist uploaded files, processors, and database managers across user interactions
- **User Interface**: Simple file upload interface with download capabilities for processed data

### Backend Architecture
- **Modular Design**: Three main components separated into distinct modules:
  - `app.py`: Main Streamlit application and user interface
  - `ifc_processor.py`: IFC file parsing and data extraction logic
  - `database_manager.py`: SQLite database operations and data management

### Data Processing Pipeline
- **IFC File Handling**: Uses ifcopenshell library for parsing IFC building data files
- **Element Type Selection**: Users can choose between IfcVirtualElement and IfcBuildingElementProxy objects
- **Data Extraction**: Extracts selected element types and tracks them with status management
- **Change Detection**: Compares new uploads with existing database to identify new and deleted objects
- **Timestamp Tracking**: Uses IFC file creation timestamps for accurate change tracking

### Data Storage
- **Database**: SQLite in-memory database for temporary data storage during session
- **Design Choice**: In-memory storage chosen for simplicity and to avoid file system dependencies
- **Data Structure**: Tables created dynamically based on IFC entity types and properties
- **Column Safety**: Implements table and column name sanitization for SQL injection prevention

### Error Handling and Logging
- **Logging**: Comprehensive logging throughout the application for debugging and monitoring
- **Exception Handling**: Try-catch blocks around critical operations like file loading and database operations
- **User Feedback**: Error messages displayed through Streamlit interface

## External Dependencies

### Core Libraries
- **Streamlit**: Web application framework for the user interface
- **ifcopenshell**: Specialized library for reading and manipulating IFC building data files
- **SQLite3**: Built-in Python database for data storage and manipulation
- **Pandas**: Data manipulation and analysis, likely used for data export and display
- **Tempfile**: For handling temporary file operations during upload processing

### File Processing
- **Zipfile**: For creating downloadable archives of processed data
- **BytesIO**: For in-memory file operations and downloads

### System Dependencies
- **OS**: Operating system interface for file path operations
- **Logging**: Python's built-in logging system for application monitoring