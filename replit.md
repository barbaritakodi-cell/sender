# LBK-DevTools Email Sender

## Overview
A Streamlit-based bulk email sender application that supports both SMTP and Gmail API for sending personalized emails to multiple recipients. The application allows users to upload contact lists (CSV, Excel, or TXT format) and send customized emails with template variables.

## Recent Changes
- **2025-11-12**: GitHub import setup on Replit (Latest)
  - Installed Python 3.11 and all required dependencies via packager tool
  - Configured Streamlit to run on port 5000 with 0.0.0.0 host binding for Replit proxy compatibility
  - Set up workflow for automatic startup on deployment
  - Created .gitignore to exclude credentials and token files while preserving Replit config
  - Fixed `use_ssl` variable initialization to prevent unbound variable errors
  - Configured deployment with autoscale target for production readiness
  - All workflows tested and running successfully
- **Previous**: Enhanced SMTP configuration and added attachment support
  - Added SMTP provider presets (Gmail, Outlook, Yahoo, Office365, iCloud) with automatic port/security configuration
  - Implemented SSL/STARTTLS security options for all SMTP types
  - Added file attachment support for both SMTP and Gmail API methods
  - Created file upload UI with session state management for attachments

## Project Architecture

### Main Components
1. **app.py**: Main Streamlit application with UI for email configuration and sending
2. **email_sender.py**: SMTP email sender class with connection testing and bulk sending
3. **gmail_sender.py**: Gmail API sender class with OAuth2 authentication
4. **utils.py**: Utility functions for file processing, validation, and data cleaning
5. **templates/email_template.html**: Sample HTML email template

### Features
- **Dual sending methods**: SMTP or Gmail API
- **SMTP provider presets**: Quick configuration for Gmail, Outlook, Yahoo, Office365, and iCloud
- **SSL/STARTTLS support**: Secure email transmission with flexible security options
- **File attachment support**: Attach multiple files to all emails (SMTP and Gmail API)
- **File upload support**: CSV, Excel (.xlsx, .xls), and TXT formats
- **Email personalization**: Template variables ({{nom}}, {{email}}, {{entreprise}}, etc.)
- **Session management**: Unique session IDs to prevent conflicts in multi-user environment
- **Gmail API OAuth2**: Secure authentication with detailed step-by-step instructions
- **Preview functionality**: Test email rendering before sending
- **Bulk sending**: Send to multiple contacts with customizable delays
- **Error tracking**: Detailed logging of success/failure for each email

### Technology Stack
- **Framework**: Streamlit 1.51.0
- **Email**: smtplib (built-in), Gmail API
- **Data Processing**: pandas, openpyxl
- **Google APIs**: google-api-python-client, google-auth-oauthlib
- **Python**: 3.11

## Configuration

### Environment Variables
The app supports the following optional environment variables:
- `SMTP_SERVER`: Default SMTP server (default: smtp.gmail.com)
- `SMTP_PORT`: Default SMTP port (default: 587)
- `SENDER_EMAIL`: Default sender email address
- `SENDER_PASSWORD`: Default sender password/app password
- `SENDER_NAME`: Default sender display name
- `GMAIL_SENDER_NAME`: Default Gmail API sender name

### Port Configuration
- **Frontend**: Runs on port 5000 (bound to 0.0.0.0)
- **Host**: Configured for all hosts to work with Replit's proxy

## Running the Application

The application runs automatically via the configured workflow:
```bash
streamlit run app.py --server.port=5000 --server.address=0.0.0.0 --server.headless=true --browser.gatherUsageStats=false
```

## File Upload Format

### CSV/Excel Files
Must contain at minimum an `email` column. Optional columns:
- `nom` (last name)
- `prenom` (first name)
- `entreprise` (company)
- Any custom fields for template variables

### TXT Files
- One email per line, or
- Comma/semicolon/tab-separated emails

## Gmail API Setup
1. Create a Google Cloud project
2. Enable Gmail API
3. Create OAuth 2.0 credentials (Desktop app type)
4. Download credentials.json
5. Upload to the application
6. Complete OAuth flow with authorization code

## Security Notes
- Credentials and token files are excluded from git
- Session-specific token files prevent user conflicts
- OAuth2 flow uses out-of-band redirect for Replit compatibility
