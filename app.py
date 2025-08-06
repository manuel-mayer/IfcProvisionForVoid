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
    st.title("🏗️ IFC File Processor")
    st.markdown("Upload and manipulate IFC building data files with ease")
    
    # Initialize session state
    if 'processor' not in st.session_state:
        st.session_state.processor = None
    if 'db_manager' not in st.session_state:
        st.session_state.db_manager = None
    if 'uploaded_file_name' not in st.session_state:
        st.session_state.uploaded_file_name = None
    if 'current_table' not in st.session_state:
        st.session_state.current_table = None
    if 'selected_element_type' not in st.session_state:
        st.session_state.selected_element_type = 'IfcVirtualElement'
    if 'user_role' not in st.session_state:
        st.session_state.user_role = 'architect'
    
    # Sidebar for file operations
    with st.sidebar:
        st.header("File Operations")
        
        # User role selection
        st.subheader("👤 User Profile")
        user_role = st.selectbox(
            "Select your role:",
            options=["architect", "structural_engineer"],
            index=0 if st.session_state.user_role == "architect" else 1,
            format_func=lambda x: "Architect" if x == "architect" else "Structural Engineer",
            help="Your role determines which approvals you can set in the database"
        )
        
        # Update user role in session state
        if user_role != st.session_state.user_role:
            st.session_state.user_role = user_role
            st.success(f"Role changed to: {'Architect' if user_role == 'architect' else 'Structural Engineer'}")
        
        st.markdown("---")
        
        # Element type selection
        st.subheader("🔧 Processing Options")
        element_type = st.selectbox(
            "Choose element type to extract:",
            options=["IfcVirtualElement", "IfcBuildingElementProxy"],
            index=0 if st.session_state.selected_element_type == "IfcVirtualElement" else 1,
            help="Select which type of IFC elements to track in the database"
        )
        
        # Update session state if changed
        if element_type != st.session_state.selected_element_type:
            st.session_state.selected_element_type = element_type
            # Clear processor to force reprocessing with new element type
            if st.session_state.processor is not None:
                st.session_state.processor = None
                st.info("Element type changed. Please re-upload your file to process with the new element type.")
        
        st.markdown("---")
        
        # File upload
        uploaded_file = st.file_uploader(
            "Choose an IFC file",
            type=['ifc'],
            help="Upload an IFC file to process"
        )
        
        if uploaded_file is not None:
            if st.session_state.uploaded_file_name != uploaded_file.name:
                st.session_state.uploaded_file_name = uploaded_file.name
                process_uploaded_file(uploaded_file, uploaded_file.name)
        
        # File download section
        if st.session_state.processor is not None:
            st.markdown("---")
            st.subheader("Export")
            
            if st.button("📥 Download Modified IFC", type="primary"):
                download_modified_ifc()
            
            if st.button("📊 Download SQLite Database"):
                download_database()
    
    # Main content area
    if st.session_state.processor is None:
        # Welcome screen
        st.info("👆 Please upload an IFC file to get started")
        
        role_display = "Architect" if st.session_state.user_role == "architect" else "Structural Engineer"
        
        st.markdown("### About this tool")
        st.markdown(f"""
        This application tracks **{st.session_state.selected_element_type}** objects from IFC building files and manages them with status tracking:
        
        - **Upload IFC files** containing {st.session_state.selected_element_type} objects
        - **Track object status** - automatically detects new and deleted objects between file versions
        - **Manage approvals** - track architect and structural engineer approvals based on your role
        - **View history** - see when objects were added or deleted with timestamps from IFC file creation dates
        - **Export database** - download the complete tracking database
        
        **Your role: {role_display}**
        - You can edit: {'Architect' if st.session_state.user_role == 'architect' else 'Structural Engineer'} approvals
        - You can view: All approvals and object status
        
        **Key features:**
        - Compares new uploads with existing database to detect changes
        - Uses IFC file timestamps for accurate change tracking
        - Maintains object lifecycle with active/deleted status management
        - Role-based approval system for proper workflow management
        
        **Element types supported:**
        - **IfcVirtualElement**: Openings, provisions for voids
        - **IfcBuildingElementProxy**: Generic building elements, placeholders
        
        **File requirements:** IFC files with the selected element type
        """)
        
    else:
        # Show file processing interface
        display_file_interface()

def process_uploaded_file(uploaded_file, original_filename):
    """Process the uploaded IFC file"""
    try:
        with st.spinner("Processing IFC file..."):
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".ifc") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_file_path = tmp_file.name
            
            # Initialize processor and database manager
            st.session_state.processor = IFCProcessor(tmp_file_path)
            st.session_state.db_manager = DatabaseManager()
            
            # Process the file with selected element type and original filename
            success = st.session_state.processor.load_ifc_to_database(
                st.session_state.db_manager, 
                st.session_state.selected_element_type,
                original_filename
            )
            
            if success:
                st.success(f"✅ Successfully processed '{uploaded_file.name}'")
                st.rerun()
            else:
                st.error("❌ Failed to process the IFC file")
                st.session_state.processor = None
                st.session_state.db_manager = None
            
            # Clean up temporary file
            os.unlink(tmp_file_path)
            
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        st.session_state.processor = None
        st.session_state.db_manager = None

def display_file_interface():
    """Display the main interface for file manipulation"""
    
    # File information
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader(f"📄 {st.session_state.uploaded_file_name}")
    
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
            
            with col1:
                # Status filter
                status_options = ['All'] + list(df['status'].unique()) if 'status' in df.columns else ['All']
                selected_status = st.selectbox("Filter by Status:", status_options)
                
            with col2:
                # Filename filter
                filename_options = ['All'] + list(df['filename'].unique()) if 'filename' in df.columns else ['All']
                selected_filename = st.selectbox("Filter by File:", filename_options)
                
            with col3:
                # Date range
                if 'added_timestamp' in df.columns:
                    show_date_filter = st.checkbox("Filter by Date Range")
        
        # Apply filters
        filtered_df = df.copy()
        
        if selected_status != 'All' and 'status' in df.columns:
            filtered_df = filtered_df[filtered_df['status'] == selected_status]
        
        if selected_filename != 'All' and 'filename' in df.columns:
            filtered_df = filtered_df[filtered_df['filename'] == selected_filename]
        
        # Display filtered data
        if not filtered_df.empty:
            # Configure columns based on user role
            column_config = {}
            disabled_cols = ['guid']  # GUID should not be editable
            user_role = st.session_state.user_role
            
            # Show role-based info
            role_display = "Architect" if user_role == "architect" else "Structural Engineer"
            st.info(f"👤 Logged in as: **{role_display}** - You can edit {role_display.lower()} approvals")
            
            if 'approval_architect' in filtered_df.columns:
                if user_role == 'architect':
                    column_config['approval_architect'] = st.column_config.CheckboxColumn(
                        "Architect Approval ✓",
                        help="Toggle architect approval (you can edit this)"
                    )
                else:
                    disabled_cols.append('approval_architect')
                    column_config['approval_architect'] = st.column_config.CheckboxColumn(
                        "Architect Approval (read-only)",
                        help="Only architects can edit this approval"
                    )
            
            if 'approval_structure' in filtered_df.columns:
                if user_role == 'structural_engineer':
                    column_config['approval_structure'] = st.column_config.CheckboxColumn(
                        "Structural Approval ✓", 
                        help="Toggle structural engineer approval (you can edit this)"
                    )
                else:
                    disabled_cols.append('approval_structure')
                    column_config['approval_structure'] = st.column_config.CheckboxColumn(
                        "Structural Approval (read-only)",
                        help="Only structural engineers can edit this approval"
                    )
            
            if 'status' in filtered_df.columns:
                column_config['status'] = st.column_config.SelectboxColumn(
                    "Status",
                    options=['active', 'deleted'],
                    help="Object status (all users can edit)"
                )
            
            # Data editor
            edited_df = st.data_editor(
                filtered_df,
                use_container_width=True,
                disabled=disabled_cols,
                column_config=column_config,
                hide_index=True,
                key="ifc_objects_editor"
            )
            
            # Save changes button
            if st.button("💾 Save Changes to Database", type="primary"):
                save_ifc_objects_changes(edited_df)
            
            # Show record count
            st.caption(f"Showing {len(filtered_df)} of {len(df)} total records")
            
        else:
            st.info("No records match the current filters.")
            
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

if __name__ == "__main__":
    main()
