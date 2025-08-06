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
    
    # Sidebar for file operations
    with st.sidebar:
        st.header("File Operations")
        
        # File upload
        uploaded_file = st.file_uploader(
            "Choose an IFC file",
            type=['ifc'],
            help="Upload an IFC file to process"
        )
        
        if uploaded_file is not None:
            if st.session_state.uploaded_file_name != uploaded_file.name:
                st.session_state.uploaded_file_name = uploaded_file.name
                process_uploaded_file(uploaded_file)
        
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
        
        st.markdown("### About this tool")
        st.markdown("""
        This application allows you to:
        - **Upload IFC files** and parse their structure
        - **View building data** in organized tables
        - **Edit properties** of building elements
        - **Export modified files** back to IFC format
        
        **Supported file format:** IFC (Industry Foundation Classes)
        """)
        
    else:
        # Show file processing interface
        display_file_interface()

def process_uploaded_file(uploaded_file):
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
            
            # Process the file
            success = st.session_state.processor.load_ifc_to_database(st.session_state.db_manager)
            
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
    
    # Get available tables
    tables = st.session_state.db_manager.get_tables()
    
    if not tables:
        st.warning("No data tables found in the processed file.")
        return
    
    # Table selection
    st.markdown("### Select Data to View/Edit")
    selected_table = st.selectbox(
        "Choose a data table:",
        options=tables,
        help="Select which type of building data you want to view or edit"
    )
    
    if selected_table:
        st.session_state.current_table = selected_table
        display_table_data(selected_table)

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
