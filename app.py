import streamlit as st
import tempfile
import os
import sqlite3
import pandas as pd
from io import BytesIO
import zipfile
from ifc_processor import IFCProcessor
from database_manager import DatabaseManager

# Configure page
st.set_page_config(
    page_title="IFC File Processor",
    page_icon="🏗️",
    layout="wide"
)

def main():
    st.title("🏗️ IFC ProvisionForVoid Tracker")
    st.markdown("Upload and manipulate IFC ProvisionForVoid data files with ease")

    # Show app description only if no IFC files are uploaded
    if not st.session_state.get('uploaded_files'):
        role_display = "Architect" if st.session_state.get('user_role', 'architect') == "architect" else "Structural Engineer"
        st.markdown(f'''
**About this tool**

This application tracks **{st.session_state.get('selected_element_type', 'IfcVirtualElement')}** objects from multiple IFC files and manages them with status tracking:

- **Upload multiple IFC files** containing {st.session_state.get('selected_element_type', 'IfcVirtualElement')} objects
- **Track object status** - automatically detects new and deleted objects between file versions
- **Manage approvals** - track architect and structural engineer approvals based on your role
- **Cross-trade coordination** - view and manage objects from all trades in one unified database
- **View history** - see when objects were added or deleted with timestamps from IFC file creation dates
- **Export database** - download the complete tracking database with all trades

**Your role: {role_display}**
- You can edit: {'Architect' if st.session_state.get('user_role', 'architect') == 'architect' else 'Structural Engineer'} approvals
- You can view: All approvals and object status from all trades

**Key features:**
- Multi-file upload support
- Compares new uploads with existing database to detect changes
- Uses IFC file timestamps for accurate change tracking
- Maintains object lifecycle with active/deleted status management
- Role-based approval system for proper workflow management
- Unified database tracking across multiple IFC files

**Element types supported:**
- **IfcVirtualElement**: Openings, provisions for voids
- **IfcBuildingElementProxy**: Generic building elements, placeholders
''')
    
    # Initialize session state
    if 'processors' not in st.session_state:
        st.session_state.processors = {}  # Dictionary to store multiple processors
    if 'db_manager' not in st.session_state:
        st.session_state.db_manager = DatabaseManager()  # Initialize once
    if 'uploaded_files' not in st.session_state:
        st.session_state.uploaded_files = []  # List of uploaded filenames
    if 'current_table' not in st.session_state:
        st.session_state.current_table = None
    if 'selected_element_type' not in st.session_state:
        st.session_state.selected_element_type = 'IfcVirtualElement'
    if 'user_role' not in st.session_state:
        st.session_state.user_role = 'architect'
    if 'db_file_path' not in st.session_state:
        st.session_state.db_file_path = None

    # Sidebar for file operations
    with st.sidebar:
        # User role selection
        user_role = st.selectbox(
            "👤 Select your role:",
            options=["architect", "structural_engineer"],
            index=0 if st.session_state.user_role == "architect" else 1,
            format_func=lambda x: "Architect" if x == "architect" else "Structural Engineer",
            help="Your role determines which approvals you can set in the database"
        )
        # Update user role in session state
        if user_role != st.session_state.user_role:
            st.session_state.user_role = user_role
            st.success(f"Role changed to: {'Architect' if user_role == 'architect' else 'Structural Engineer'}")
        # Element type selection
        element_type = st.selectbox(
            "🔧 Choose element type to extract:",
            options=["IfcVirtualElement", "IfcBuildingElementProxy"],
            index=0 if st.session_state.selected_element_type == "IfcVirtualElement" else 1,
            help="Select which type of IFC elements to track in the database"
        )
        
        # Update session state if changed
        if element_type != st.session_state.selected_element_type:
            st.session_state.selected_element_type = element_type
            # Clear processors to force reprocessing with new element type
            if st.session_state.uploaded_files:
                st.session_state.processors = {}
                st.session_state.uploaded_files = []
                st.info("Element type changed. Please re-upload your files to process with the new element type.")
        

        # Upload existing database file section (no divider)
        uploaded_db = st.file_uploader(
            "📂 Upload existing database SQLite file:",
            type=['db'],
            accept_multiple_files=False,
            help="Upload an existing SQLite database file"
        )
        if uploaded_db is not None:
            # Save uploaded DB to a temp file and re-initialize DatabaseManager
            with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp_db:
                tmp_db.write(uploaded_db.getvalue())
                tmp_db_path = tmp_db.name
            # Re-initialize DatabaseManager with the uploaded DB file
            st.session_state.db_manager = DatabaseManager(tmp_db_path)
            st.session_state.db_file_path = tmp_db_path
            st.success(f"Using uploaded database: {uploaded_db.name}")
            # Optionally clear uploaded files and processors to avoid mismatch
            st.session_state.uploaded_files = []
            st.session_state.processors = {}

        # Multiple file upload
        uploaded_files = st.file_uploader(
            "📂 Upload IFC files:",
            type=['ifc'],
            accept_multiple_files=True,
            help="Upload multiple IFC files to process and track in the same database"
        )
        
        if uploaded_files:
            # Process new files
            for uploaded_file in uploaded_files:
                if uploaded_file.name not in st.session_state.uploaded_files:
                    st.session_state.uploaded_files.append(uploaded_file.name)
                    process_uploaded_file(uploaded_file, uploaded_file.name)
            
            # Display uploaded files
            st.markdown("**Uploaded Files:**")
            for filename in st.session_state.uploaded_files:
                st.markdown(f"• {filename}")
            # Add clear all files button
            if st.button("🗑️ Clear All Files"):
                st.session_state.uploaded_files = []
                st.session_state.processors = {}
                st.rerun()

        # Bulk approval by GUID section (only if IFC files uploaded)
        if st.session_state.uploaded_files:
            st.markdown("---")
            st.subheader("✅ Bulk Approve by GUID")
            st.markdown("Paste one or more GUIDs (one per line or comma-separated) to approve them in the database.")
            guid_input = st.text_area(
                "Enter GUIDs to approve:",
                placeholder="Paste GUIDs here...",
                height=100,
                key="bulk_guid_input"
            )
            if st.button("Approve Selected GUIDs"):
                if guid_input.strip():
                    # Parse GUIDs (split by comma, semicolon, or newline)
                    import re
                    guid_list = [g.strip() for g in re.split(r'[\n,;]+', guid_input) if g.strip()]
                    if guid_list:
                        # Get current approval column based on user role
                        role = st.session_state.user_role
                        approval_col = 'approval_architect' if role == 'architect' else 'approval_structure'
                        try:
                            # Get current table
                            df = st.session_state.db_manager.get_table_data('ifc_objects')
                            if approval_col in df.columns and 'guid' in df.columns:
                                # Update approval for matching GUIDs
                                updated = 0
                                for guid in guid_list:
                                    idx = df[df['guid'] == guid].index
                                    if not idx.empty:
                                        df.loc[idx, approval_col] = True
                                        updated += len(idx)
                                if updated > 0:
                                    st.session_state.db_manager.update_table_data('ifc_objects', df)
                                    st.success(f"Approved {updated} object(s) for role: {'Architect' if role == 'architect' else 'Structural Engineer'}.")
                                else:
                                    st.warning("No matching GUIDs found in the database.")
                            else:
                                st.error("Database does not contain the required columns.")
                        except Exception as e:
                            st.error(f"Error updating approvals: {str(e)}")
                    else:
                        st.warning("No valid GUIDs entered.")
                else:
                    st.warning("Please enter at least one GUID.")

        # File download section
        if st.session_state.uploaded_files:
            st.markdown("---")
            st.subheader("Export")
            # .db download button (single instance)
            db_content = st.session_state.db_manager.get_database_content()
            st.download_button(
                label="📊 Download Database (.db)",
                data=db_content,
                file_name="ifc_database.db",
                mime="application/octet-stream",
                help="Download the SQLite database containing the extracted IFC data",
                key="db_download_button"
            )
            # Excel download button (streamlined, always visible)
            # Generate Excel in memory and show download button
            try:
                df = st.session_state.db_manager.get_table_data('ifc_objects')
                if not df.empty:
                    from io import BytesIO
                    import pandas as pd
                    excel_buffer = BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                        df.to_excel(writer, sheet_name='IFC_Objects', index=False)
                        # Auto-adjust column widths
                        worksheet = writer.sheets['IFC_Objects']
                        for column in worksheet.columns:
                            max_length = 0
                            column_letter = column[0].column_letter
                            for cell in column:
                                try:
                                    if len(str(cell.value)) > max_length:
                                        max_length = len(str(cell.value))
                                except:
                                    pass
                            adjusted_width = min(max_length + 2, 50)
                            worksheet.column_dimensions[column_letter].width = adjusted_width
                        # Add a summary sheet
                        summary_data = {
                            'Metric': ['Total Objects', 'Active Objects', 'Deleted Objects', 
                                      'Architect Approved', 'Structure Approved', 'IFC Files'],
                            'Count': [
                                len(df),
                                len(df[df['status'] == 'active']) if 'status' in df.columns else len(df),
                                len(df[df['status'] == 'deleted']) if 'status' in df.columns else 0,
                                len(df[df['approval_architect'] == True]) if 'approval_architect' in df.columns else 0,
                                len(df[df['approval_structure'] == True]) if 'approval_structure' in df.columns else 0,
                                df['filename'].nunique() if 'filename' in df.columns else 1
                            ]
                        }
                        summary_df = pd.DataFrame(summary_data)
                        summary_df.to_excel(writer, sheet_name='Summary', index=False)
                    excel_buffer.seek(0)
                    st.download_button(
                        label="📋 Download Database as Excel (.xlsx)",
                        data=excel_buffer.getvalue(),
                        file_name="ifc_database.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        help="Download the database as an Excel spreadsheet for easy review"
                    )
                else:
                    st.info("No data found in database to export as Excel.")
            except Exception as e:
                st.error(f"Error preparing Excel file: {str(e)}")

            # --- IFC Write-back Section ---
        st.markdown("---")
        st.subheader("Write Approvals Back to IFC")
        st.markdown("Export all uploaded IFC files with the current approval status written back from the database.")
        if st.button("⬇️ Download All IFCs with Approvals"):
            try:
                import ifcopenshell
                import ifcopenshell.api
                import tempfile
                df = st.session_state.db_manager.get_table_data('ifc_objects')
                approved_objects_dict = {row['guid']: row for _, row in df.iterrows()}
                element_types = ["IfcVirtualElement", "IfcBuildingElementProxy"]
                updated_any = False
                for uploaded_file in st.session_state.processors:
                    processor = st.session_state.processors[uploaded_file]
                    uploaded_file_obj = getattr(processor, 'ifc_file_path', None)
                    if not uploaded_file_obj:
                        continue
                    try:
                        ifc_file = ifcopenshell.open(uploaded_file_obj)
                        all_ifc_objects = []
                        for etype in element_types:
                            all_ifc_objects.extend(ifc_file.by_type(etype))
                        # Only update if there are matching GUIDs
                        matching_guids = [o for o in all_ifc_objects if o.GlobalId in approved_objects_dict]
                        if not matching_guids:
                            continue
                        pset_name = "Planung"
                        architect_approval_property = "Architektur_Freigabe"
                        structure_approval_property = "Tragwerksplanung_Freigabe"
                        modified_object_count = 0
                        for ifc_object in matching_guids:
                            guid = ifc_object.GlobalId
                            approval_data = approved_objects_dict[guid]
                            try:
                                pset = ifcopenshell.api.run("pset.add_pset", ifc_file, product=ifc_object, name=pset_name)
                                properties_to_add = {
                                    architect_approval_property: str(bool(approval_data.get('approval_architect', False))),
                                    structure_approval_property: str(bool(approval_data.get('approval_structure', False)))
                                }
                                ifcopenshell.api.run("pset.edit_pset", ifc_file, pset=pset, properties=properties_to_add)
                                modified_object_count += 1
                            except Exception:
                                pass
                        if modified_object_count > 0:
                            updated_any = True
                            with tempfile.NamedTemporaryFile(delete=False, suffix="_with_approvals.ifc") as tmp_ifc:
                                ifc_file.write(tmp_ifc.name)
                                tmp_ifc.seek(0)
                                st.download_button(
                                    label=f"Download Updated {uploaded_file} ({modified_object_count} objects updated)",
                                    data=tmp_ifc.read(),
                                    file_name=f"{uploaded_file.replace('.ifc','')}_with_approvals.ifc",
                                    mime="application/octet-stream",
                                    help=f"Download the IFC file '{uploaded_file}' with approval status written back from the database."
                                )
                            st.success(f"Successfully wrote approvals to {modified_object_count} objects in {uploaded_file}.")
                    except Exception as e:
                        st.error(f"Error writing approvals to IFC '{uploaded_file}': {str(e)}")
                if not updated_any:
                    st.info("No uploaded IFC files had objects with matching GUIDs in the database.")
            except Exception as e:
                st.error(f"Error writing approvals to IFCs: {str(e)}")
        
        # ...existing code...
        
    # Show file processing interface if files are uploaded
    if st.session_state.uploaded_files:
        display_file_interface()

def process_uploaded_file(uploaded_file, original_filename):
    """Process the uploaded IFC file"""
    try:
        with st.spinner("Processing IFC file..."):
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".ifc") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name
            
            # Initialize processor for this file
            processor = IFCProcessor(tmp_file_path)
            
            # Process the file with selected element type and original filename
            success = processor.load_ifc_to_database(
                st.session_state.db_manager, 
                st.session_state.selected_element_type,
                original_filename
            )
            
            # Store processor for this file
            if success:
                st.session_state.processors[original_filename] = processor
            
            if success:
                st.success(f"✅ Successfully processed '{uploaded_file.name}'")
            else:
                st.error(f"❌ Failed to process '{uploaded_file.name}'")
            
            # Clean up temporary file
            os.unlink(tmp_file_path)
            
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")

def display_file_interface():
    """Display the main interface for file manipulation"""
    
    # File information
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader(f"📄 Multi-Trade IFC Database ({len(st.session_state.uploaded_files)} files)")
    
    with col2:
        if st.button("🔄 Refresh Data"):
            st.rerun()
    
    # Show IFC Objects table (main table from your workflow)
    element_type = st.session_state.selected_element_type
    st.markdown(f"### IFC {element_type} Database")
    st.markdown(f"This table tracks **{element_type}** objects from your IFC files with status management.")
    
    # Get the main ifc_objects table
    try:
        df = st.session_state.db_manager.get_table_data('ifc_objects')
        
        if df.empty:
            st.info(f"No IFC objects found. Make sure your IFC file contains {element_type} objects.")
        else:
            # Display summary statistics
            col1, col2, col3, col4, col5, col6 = st.columns(6)
            with col1:
                active_count = len(df[df['status'] == 'active']) if 'status' in df.columns else len(df)
                st.metric("Active Objects", active_count)
            with col2:
                deleted_count = len(df[df['status'] == 'deleted']) if 'status' in df.columns else 0
                st.metric("Deleted Objects", deleted_count)
            with col3:
                total_files = df['filename'].nunique() if 'filename' in df.columns else 1
                st.metric("IFC Files", total_files)
            with col4:
                st.metric("Total Records", len(df))
            with col5:
                if 'approval_architect' in df.columns:
                    arch_approved = len(df[df['approval_architect'] == True]) if 'approval_architect' in df.columns else 0
                    st.metric("Architect Approved", arch_approved)
                else:
                    st.metric("Architect Approved", "N/A")
            with col6:
                if 'approval_structure' in df.columns:
                    struct_approved = len(df[df['approval_structure'] == True]) if 'approval_structure' in df.columns else 0
                    st.metric("Structure Approved", struct_approved)
                else:
                    st.metric("Structure Approved", "N/A")
            
            # Display the table
            display_ifc_objects_table(df)
            
    except Exception as e:
        st.error(f"Error loading IFC objects: {str(e)}")
        # Fallback to show available tables
        tables = st.session_state.db_manager.get_tables()
        if tables:
            st.markdown("### Available Tables")
            selected_table = st.selectbox("Choose a table:", options=tables)
            if selected_table:
                display_table_data(selected_table)

def display_ifc_objects_table(df):
    """Display and allow editing of the main ifc_objects table"""
    try:
        st.markdown("#### Edit Object Status and Approvals")
        st.markdown("You can edit the status and approval columns directly in the table below.")
        
        # Filter options
        with st.expander("🔍 Filter Options"):
            col1, col2, col3 = st.columns(3)
            
        # Status filter
        status_options = ['All'] + list(df['status'].unique()) if 'status' in df.columns else ['All']
        selected_status = st.selectbox("Filter by Status:", status_options)
        # ...existing code for other filters and table display...
            
    except Exception as e:
        st.error(f"Error displaying IFC objects table: {str(e)}")

def save_ifc_objects_changes(edited_df):
    """Save changes to the ifc_objects table"""
    try:
        with st.spinner("Saving changes to database..."):
            success = st.session_state.db_manager.update_table_data('ifc_objects', edited_df)
            
            if success:
                st.success("✅ Changes saved successfully!")
            else:
                st.error("❌ Failed to save changes")
    
    except Exception as e:
        st.error(f"Error saving changes: {str(e)}")

def display_table_data(table_name):
    """Display and allow editing of table data"""
    try:
        # Get table data
        df = st.session_state.db_manager.get_table_data(table_name)
        
        if df.empty:
            st.info(f"No data found in table '{table_name}'")
            return
        
        st.markdown(f"### 📊 {table_name}")
        st.markdown(f"**Records found:** {len(df)}")
        
        # Display table statistics
        with st.expander("📈 Table Statistics"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Records", len(df))
            with col2:
                st.metric("Columns", len(df.columns))
            with col3:
                numeric_cols = df.select_dtypes(include=['number']).columns
                st.metric("Numeric Columns", len(numeric_cols))
        
        # Data editing interface
        st.markdown("#### Edit Data")
        
        # Option to filter data
        if len(df) > 100:
            st.info("💡 Large dataset detected. Use filters to focus on specific records.")
            
            # Add simple filtering
            if st.checkbox("Enable Filtering"):
                filter_column = st.selectbox("Filter by column:", df.columns)
                if filter_column:
                    unique_values = df[filter_column].unique()
                    if len(unique_values) > 50:
                        filter_value = st.text_input(f"Filter {filter_column} contains:")
                        if filter_value:
                            df = df[df[filter_column].astype(str).str.contains(filter_value, case=False, na=False)]
                    else:
                        filter_values = st.multiselect(f"Select {filter_column} values:", unique_values)
                        if filter_values:
                            df = df[df[filter_column].isin(filter_values)]
        
        # Data editor
        if not df.empty:
            edited_df = st.data_editor(
                df,
                use_container_width=True,
                num_rows="dynamic",
                disabled=["GlobalId"] if "GlobalId" in df.columns else None,
                help="Edit the data directly in the table. Changes will be saved to the database."
            )
            
            # Save changes button
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("💾 Save Changes", type="primary"):
                    save_table_changes(table_name, edited_df)
            
            with col2:
                if st.button("↩️ Reset to Original"):
                    st.rerun()
        
        else:
            st.info("No records match the current filters.")
    
    except Exception as e:
        st.error(f"Error displaying table data: {str(e)}")

def save_table_changes(table_name, edited_df):
    """Save changes back to the database"""
    try:
        with st.spinner("Saving changes..."):
            success = st.session_state.db_manager.update_table_data(table_name, edited_df)
            
            if success:
                st.success("✅ Changes saved successfully!")
                # Update the IFC model
                st.session_state.processor.update_ifc_from_database(st.session_state.db_manager)
            else:
                st.error("❌ Failed to save changes")
    
    except Exception as e:
        st.error(f"Error saving changes: {str(e)}")

def download_modified_ifc():
    """Provide download link for modified IFC file"""
    try:
        with st.spinner("Preparing IFC file for download..."):
            # Update IFC from database
            st.session_state.processor.update_ifc_from_database(st.session_state.db_manager)
            
            # Get the modified IFC content
            ifc_content = st.session_state.processor.get_ifc_content()
            
            if ifc_content:
                # Create download
                original_name = st.session_state.uploaded_file_name
                new_name = f"modified_{original_name}"
                
                st.download_button(
                    label="📥 Download Modified IFC",
                    data=ifc_content,
                    file_name=new_name,
                    mime="application/octet-stream",
                    help="Download the IFC file with your modifications applied"
                )
            else:
                st.error("Failed to generate modified IFC file")
    
    except Exception as e:
        st.error(f"Error preparing download: {str(e)}")

def download_database():
    """Provide download link for SQLite database"""
    try:
        db_content = st.session_state.db_manager.get_database_content()
        
        if db_content:
            st.download_button(
                label="📊 Download Database",
                data=db_content,
                file_name="ifc_data.db",
                mime="application/octet-stream",
                help="Download the SQLite database containing the extracted IFC data"
            )
        else:
            st.error("Failed to prepare database for download")
    
    except Exception as e:
        st.error(f"Error preparing database download: {str(e)}")

def download_excel_database():
    """Export database to Excel and provide download link"""
    try:
        with st.spinner("Converting database to Excel format..."):
            # Get the ifc_objects data
            df = st.session_state.db_manager.get_table_data('ifc_objects')
            
            if df.empty:
                st.warning("No data found in database to export")
                return
            
            # Create Excel file in memory
            from io import BytesIO
            excel_buffer = BytesIO()
            
            # Write DataFrame to Excel
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='IFC_Objects', index=False)
                
                # Get the workbook and worksheet
                workbook = writer.book
                worksheet = writer.sheets['IFC_Objects']
                
                # Auto-adjust column widths
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
                
                # Add a summary sheet with statistics
                summary_data = {
                    'Metric': ['Total Objects', 'Active Objects', 'Deleted Objects', 
                              'Architect Approved', 'Structure Approved', 'IFC Files'],
                    'Count': [
                        len(df),
                        len(df[df['status'] == 'active']) if 'status' in df.columns else len(df),
                        len(df[df['status'] == 'deleted']) if 'status' in df.columns else 0,
                        len(df[df['approval_architect'] == True]) if 'approval_architect' in df.columns else 0,
                        len(df[df['approval_structure'] == True]) if 'approval_structure' in df.columns else 0,
                        df['filename'].nunique() if 'filename' in df.columns else 1
                    ]
                }
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            excel_buffer.seek(0)
            
            # Generate filename based on current timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"IFC_Database_{timestamp}.xlsx"
            
            st.download_button(
                label="📋 Download Excel File",
                data=excel_buffer.getvalue(),
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Download the database as an Excel spreadsheet for easy review"
            )
            
            st.success(f"✅ Excel file ready for download ({len(df)} records)")
    
    except Exception as e:
        st.error(f"Error creating Excel file: {str(e)}")

if __name__ == "__main__":
    # Run the app with the specified address and port
    main()