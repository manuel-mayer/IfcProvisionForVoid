# IFC File Processor

A Streamlit web application for processing and managing IFC (Industry Foundation Classes) building data files from multiple trades. This tool allows architects and structural engineers to upload IFC files, extract building elements, track changes, and manage approvals in a collaborative workflow.

## Features

- **Multi-Trade Support**: Upload and process IFC files from different trades (structural, MEP, architectural, etc.)
- **Element Extraction**: Extract IfcVirtualElement or IfcBuildingElementProxy objects
- **Change Tracking**: Automatically detect new and deleted objects between file versions
- **Role-Based Approvals**: Architect and structural engineer approval workflow
- **Database Management**: SQLite database for persistent object tracking
- **Export Options**: Export data as Excel, IFC files, or SQLite database
- **Cross-Trade Coordination**: View and manage objects from all trades in one unified interface

## Installation

1. Clone this repository:
```bash
git clone https://github.com/YOUR_USERNAME/ifc-file-processor.git
cd ifc-file-processor
```

2. Install dependencies using uv:
```bash
uv sync
```

3. Run the application:
```bash
uv run streamlit run app.py --server.port 5000
```

## Usage

1. **Select Your Role**: Choose between Architect or Structural Engineer
2. **Choose Element Type**: Select IfcVirtualElement or IfcBuildingElementProxy
3. **Upload IFC Files**: Upload multiple IFC files from different trades
4. **Review Data**: View extracted objects in the database table
5. **Manage Approvals**: Edit approvals based on your role
6. **Export Results**: Download Excel, IFC, or database files

## File Structure

- `app.py` - Main Streamlit application
- `ifc_processor.py` - IFC file parsing and data extraction
- `database_manager.py` - SQLite database operations
- `pyproject.toml` - Project dependencies
- `.streamlit/config.toml` - Streamlit configuration

## Dependencies

- **Streamlit**: Web application framework
- **ifcopenshell**: IFC file processing
- **pandas**: Data manipulation
- **openpyxl**: Excel file handling
- **sqlite3**: Database operations

## Development

This application was built using:
- Python 3.11+
- Streamlit for the web interface
- ifcopenshell for IFC file processing
- SQLite for data persistence

## License

MIT License - see LICENSE file for details