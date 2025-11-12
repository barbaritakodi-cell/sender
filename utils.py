import pandas as pd
import re
from typing import List, Optional, Any
import streamlit as st

def validate_email(email: str) -> bool:
    """
    Validate email address format.
    
    Args:
        email: Email address to validate
        
    Returns:
        bool: True if email is valid, False otherwise
    """
    if not email or pd.isna(email):
        return False
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, str(email)) is not None

def validate_csv_columns(df: pd.DataFrame) -> bool:
    """
    Validate that the DataFrame has required columns.
    
    Args:
        df: DataFrame to validate
        
    Returns:
        bool: True if DataFrame has required columns, False otherwise
    """
    required_columns = ['email']
    
    # Convert column names to lowercase for case-insensitive comparison
    df_columns_lower = [col.lower() for col in df.columns]
    
    for required_col in required_columns:
        if required_col.lower() not in df_columns_lower:
            return False
    
    return True

def process_uploaded_file(uploaded_file) -> pd.DataFrame:
    """
    Process uploaded CSV, Excel or TXT file and return DataFrame.
    
    Args:
        uploaded_file: Streamlit uploaded file object
        
    Returns:
        pd.DataFrame: Processed DataFrame with contact data
        
    Raises:
        Exception: If file cannot be processed
    """
    try:
        # Get file extension
        file_extension = uploaded_file.name.split('.')[-1].lower()
        
        if file_extension == 'csv':
            # Try different encodings for CSV files
            encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
            df = None
            
            for encoding in encodings:
                try:
                    uploaded_file.seek(0)  # Reset file pointer
                    df = pd.read_csv(uploaded_file, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if df is None:
                raise Exception("Unable to read CSV file with any supported encoding")
                
        elif file_extension in ['xlsx', 'xls']:
            df = pd.read_excel(uploaded_file)
            
        elif file_extension == 'txt':
            # Handle TXT files - each line should be an email or comma/semicolon separated
            encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
            content = None
            
            for encoding in encodings:
                try:
                    uploaded_file.seek(0)  # Reset file pointer
                    content = uploaded_file.read().decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if content is None:
                raise Exception("Unable to read TXT file with any supported encoding")
            
            # Parse the content
            emails = []
            lines = content.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Check if line contains separators (comma, semicolon, tab)
                if ',' in line or ';' in line or '\t' in line:
                    # Split by multiple separators
                    import re
                    parts = re.split(r'[,;\t]+', line)
                    for part in parts:
                        part = part.strip()
                        if part and validate_email(part):
                            emails.append(part)
                else:
                    # Treat as single email
                    if validate_email(line):
                        emails.append(line)
            
            # Create DataFrame
            df = pd.DataFrame({'email': emails})
            
        else:
            raise Exception(f"Unsupported file format: {file_extension}")
        
        # Clean column names (only if not TXT file)
        if file_extension != 'txt':
            df.columns = df.columns.str.strip()
            
            # Normalize column names to lowercase for easier matching
            column_mapping = {}
            for col in df.columns:
                col_lower = col.lower()
                if 'email' in col_lower or 'mail' in col_lower:
                    column_mapping[col] = 'email'
                elif 'nom' in col_lower or 'name' in col_lower:
                    column_mapping[col] = 'nom'
                elif 'prénom' in col_lower or 'prenom' in col_lower or 'firstname' in col_lower:
                    column_mapping[col] = 'prenom'
                elif 'entreprise' in col_lower or 'company' in col_lower or 'societe' in col_lower:
                    column_mapping[col] = 'entreprise'
            
            # Rename columns if mapping found
            if column_mapping:
                df = df.rename(columns=column_mapping)
        
        # Remove rows with empty email addresses
        if 'email' in df.columns:
            df = df.dropna(subset=['email'])
            df = df[df['email'].str.strip() != '']
        
        # Validate email addresses
        if 'email' in df.columns:
            valid_emails = df['email'].apply(validate_email)
            invalid_count = (~valid_emails).sum()
            
            if invalid_count > 0:
                st.warning(f"⚠️ {invalid_count} adresses email invalides détectées et supprimées.")
            
            df = df[valid_emails].copy()
        
        # Remove duplicate email addresses
        if 'email' in df.columns:
            initial_count = len(df)
            df = df.drop_duplicates(subset=['email'], keep='first')
            duplicate_count = initial_count - len(df)
            
            if duplicate_count > 0:
                st.info(f"ℹ️ {duplicate_count} doublons supprimés.")
        
        return df
        
    except Exception as e:
        raise Exception(f"Error processing file: {str(e)}")

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean DataFrame by removing empty rows and standardizing data.
    
    Args:
        df: DataFrame to clean
        
    Returns:
        pd.DataFrame: Cleaned DataFrame
    """
    # Remove completely empty rows
    df = df.dropna(how='all')
    
    # Strip whitespace from string columns
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.strip()
            # Replace 'nan' strings with actual NaN
            df[col] = df[col].replace('nan', pd.NA)
    
    return df

def get_template_variables(template: str) -> List[str]:
    """
    Extract template variables from a string template.
    
    Args:
        template: Template string with variables in {{variable}} format
        
    Returns:
        List[str]: List of variable names found in template
    """
    pattern = r'\{\{(\w+)\}\}'
    variables = re.findall(pattern, template)
    return list(set(variables))  # Remove duplicates

def validate_template_variables(template: str, available_columns: List[str]) -> List[str]:
    """
    Validate that template variables exist in available columns.
    
    Args:
        template: Template string
        available_columns: List of available column names
        
    Returns:
        List[str]: List of missing variables
    """
    template_vars = get_template_variables(template)
    available_lower = [col.lower() for col in available_columns]
    
    missing_vars = []
    for var in template_vars:
        if var.lower() not in available_lower:
            missing_vars.append(var)
    
    return missing_vars

def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        str: Formatted size string
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    size = float(size_bytes)
    while size >= 1024 and i < len(size_names) - 1:
        size /= 1024
        i += 1
    
    return f"{size:.1f} {size_names[i]}"

def create_sample_csv() -> pd.DataFrame:
    """
    Create a sample CSV DataFrame for demonstration.
    
    Returns:
        pd.DataFrame: Sample DataFrame with contact data
    """
    sample_data = {
        'email': [
            'exemple1@email.com',
            'exemple2@email.com',
            'exemple3@email.com'
        ],
        'nom': [
            'Dupont',
            'Martin',
            'Durand'
        ],
        'prenom': [
            'Jean',
            'Marie',
            'Pierre'
        ],
        'entreprise': [
            'Entreprise A',
            'Entreprise B',
            'Entreprise C'
        ]
    }
    
    return pd.DataFrame(sample_data)

def export_logs_to_csv(logs: List[dict]) -> str:
    """
    Export logs to CSV format.
    
    Args:
        logs: List of log dictionaries
        
    Returns:
        str: CSV formatted string
    """
    if not logs:
        return "email,status,timestamp,error\n"
    
    df = pd.DataFrame(logs)
    return df.to_csv(index=False)

def sanitize_html_content(content: str) -> str:
    """
    Basic HTML sanitization for email content.
    
    Args:
        content: HTML content to sanitize
        
    Returns:
        str: Sanitized HTML content
    """
    # Remove potentially dangerous tags
    dangerous_tags = ['script', 'iframe', 'object', 'embed', 'form']
    
    for tag in dangerous_tags:
        content = re.sub(f'<{tag}[^>]*>.*?</{tag}>', '', content, flags=re.IGNORECASE | re.DOTALL)
        content = re.sub(f'<{tag}[^>]*/?>', '', content, flags=re.IGNORECASE)
    
    return content
