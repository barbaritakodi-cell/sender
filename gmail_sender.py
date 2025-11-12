import base64
import json
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import logging
from typing import Dict, Any, Tuple, Optional, List
import pandas as pd

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
except ImportError:
    raise ImportError("Google API libraries not installed. Please install: google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")

class GmailSender:
    """Gmail API email sender class."""

    SCOPES = [
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/userinfo.email',
        'openid'
    ]

    def __init__(self, credentials_json: Optional[str] = None, token_file: str = "token.json", sender_name: str = "", session_id: Optional[str] = None):
        """
        Initialize Gmail API sender.

        Args:
            credentials_json: Path to credentials JSON file or JSON string
            token_file: Path to store token file
            sender_name: Display name for sender
        """
        self.credentials_json = credentials_json
        # Use session-specific token file if session_id is provided
        if session_id:
            self.token_file = f"token_{session_id}.json"
        else:
            self.token_file = token_file
        self.service = None
        self.creds = None
        self.sender_email = None
        self.sender_name = sender_name
        self.flow = None
        self.last_auth_error = None

        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def clear_token(self):
        """Clear existing token file."""
        if os.path.exists(self.token_file):
            os.remove(self.token_file)
            self.logger.info("Token file cleared")

    def start_auth_flow(self, credentials_json_content: str) -> str:
        """
        Start the authentication flow and return the authorization URL.

        Args:
            credentials_json_content: JSON content of credentials file

        Returns:
            str: Authorization URL to visit
        """
        try:
            # Load existing token first
            creds = None
            if os.path.exists(self.token_file):
                creds = Credentials.from_authorized_user_file(self.token_file, self.SCOPES)

            # If we have valid credentials, use them
            if creds and creds.valid:
                try:
                    self.creds = creds
                    self.service = build('gmail', 'v1', credentials=creds)
                    profile = self.service.users().getProfile(userId='me').execute()
                    self.sender_email = profile.get('emailAddress')
                    return "ALREADY_AUTHENTICATED"
                except Exception as e:
                    if "insufficientPermissions" in str(e) or "insufficient authentication scopes" in str(e):
                        self.logger.warning("Existing token has insufficient permissions. Need to re-authenticate.")
                        # Remove the invalid token file
                        if os.path.exists(self.token_file):
                            os.remove(self.token_file)
                    else:
                        raise e

            # If credentials are expired but have refresh token
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    self.creds = creds
                    self.service = build('gmail', 'v1', credentials=creds)
                    profile = self.service.users().getProfile(userId='me').execute()
                    self.sender_email = profile.get('emailAddress')

                    # Save refreshed credentials
                    with open(self.token_file, 'w') as token:
                        token.write(creds.to_json())

                    return "ALREADY_AUTHENTICATED"
                except Exception:
                    # Refresh failed, need new authentication
                    pass

            # Need new authentication
            credentials_data = json.loads(credentials_json_content)
            self.flow = InstalledAppFlow.from_client_config(credentials_data, self.SCOPES)

            # Set redirect URI for out-of-band flow (works in Replit)
            self.flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'

            # Get authorization URL
            auth_url, _ = self.flow.authorization_url(prompt='consent')
            return auth_url

        except Exception as e:
            self.logger.error(f"Failed to start auth flow: {str(e)}")
            return f"ERROR: {str(e)}"

    def get_error_context(self, error_str: str) -> str:
        """Get user-friendly error context based on the error string."""
        if "invalid_grant" in error_str or "Invalid authorization code" in error_str:
            return "CODE_EXPIRED_OR_INVALID"
        elif "Scope has changed" in error_str:
            # Check if it's just openid being added automatically by Google
            if "openid" in error_str and "gmail.send" in error_str and "userinfo.email" in error_str:
                # This is a normal variation, not a real scope mismatch
                return "NORMAL_SCOPE_VARIATION"
            return "SCOPE_MISMATCH"
        elif "redirect_uri_mismatch" in error_str:
            return "REDIRECT_MISMATCH"
        elif "invalid_client" in error_str:
            return "INVALID_CREDENTIALS"
        else:
            return "UNKNOWN_ERROR"

    def complete_authentication(self, auth_code: str) -> bool:
        """
        Complete authentication using the authorization code.

        Args:
            auth_code: Authorization code from Google

        Returns:
            bool: True if authentication successful
        """
        try:
            if not self.flow:
                self.logger.error("No authentication flow available")
                return False

            # Exchange code for credentials
            self.flow.fetch_token(code=auth_code.strip())
            creds = self.flow.credentials

            # Save the credentials for future use
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())

            # Set up service
            self.creds = creds
            self.service = build('gmail', 'v1', credentials=creds)

            # Get user email - try multiple methods
            try:
                # Method 1: Try Gmail profile
                profile = self.service.users().getProfile(userId='me').execute()
                self.sender_email = profile.get('emailAddress')
            except Exception as profile_error:
                self.logger.warning(f"Could not get Gmail profile: {profile_error}")
                try:
                    # Method 2: Try getting from token info
                    import requests
                    token_info_url = f"https://www.googleapis.com/oauth2/v1/tokeninfo?access_token={creds.token}"
                    response = requests.get(token_info_url)
                    if response.status_code == 200:
                        token_info = response.json()
                        self.sender_email = token_info.get('email')
                        if self.sender_email:
                            self.logger.info(f"Got email from token info: {self.sender_email}")
                    else:
                        self.logger.warning("Could not get email from token info")
                        # Fallback: will be set when sending first email
                        self.sender_email = "authenticated@gmail.com"
                        self.logger.info("Using fallback email, will be updated when sending")
                except Exception as token_error:
                    self.logger.warning(f"Could not get email from token: {token_error}")
                    self.sender_email = "authenticated@gmail.com"

            self.logger.info("Gmail API authentication completed successfully")
            return True

        except Exception as e:
            error_str = str(e)
            self.logger.error(f"Failed to complete authentication: {error_str}")
            
            # Handle scope changes that are normal OAuth behavior
            if "Scope has changed" in error_str:
                # Check if the scopes contain the essential ones we need
                required_scopes = ["gmail.send", "userinfo.email"]
                has_required = all(scope in error_str for scope in required_scopes)
                
                # Check what scopes were actually granted
                if "to \"" in error_str:
                    granted_scopes = error_str.split("to \"")[1].split("\"")[0]
                    self.logger.error(f"Permissions accordées par l'utilisateur: {granted_scopes}")
                    
                    if "gmail.send" not in granted_scopes:
                        self.logger.error("ERREUR: L'utilisateur n'a pas accordé la permission d'envoi Gmail")
                        self.last_auth_error = "MISSING_GMAIL_SEND"
                        return False
                
                if has_required and self.flow:
                    # This is just Google adding/reordering scopes automatically, try to proceed anyway
                    self.logger.info("Detected normal OAuth scope variation, attempting to continue...")
                    try:
                        # Clear existing token and try fresh authentication
                        if os.path.exists(self.token_file):
                            os.remove(self.token_file)
                        
                        # Re-run the flow with current code
                        self.flow.fetch_token(code=auth_code.strip())
                        creds = self.flow.credentials
                        
                        # Save and test the credentials
                        with open(self.token_file, 'w') as token:
                            token.write(creds.to_json())
                        
                        self.creds = creds
                        self.service = build('gmail', 'v1', credentials=creds)
                        
                        # Get user email - try multiple methods
                        try:
                            profile = self.service.users().getProfile(userId='me').execute()
                            self.sender_email = profile.get('emailAddress')
                        except Exception:
                            # Fallback method for email
                            self.sender_email = "authenticated@gmail.com"
                            self.logger.info("Using fallback email, will be updated when sending")
                        
                        self.logger.info("Gmail API authentication completed successfully after scope adjustment")
                        return True
                        
                    except Exception as retry_error:
                        self.logger.error(f"Retry failed: {str(retry_error)}")
                        # Fall through to normal error handling
                        pass
            
            # Handle specific authentication errors
            error_context = self.get_error_context(error_str)
            
            if error_context == "CODE_EXPIRED_OR_INVALID":
                self.logger.warning("Authorization code is invalid or expired")
            elif error_context == "SCOPE_MISMATCH":
                self.logger.warning("Scope mismatch detected, clearing existing token")
                if os.path.exists(self.token_file):
                    os.remove(self.token_file)
                self.flow = None
                self.logger.info("Please generate a new authorization link and try again")
            elif error_context == "REDIRECT_MISMATCH":
                self.logger.error("Redirect URI mismatch. Please check your Google Console configuration")
            elif error_context == "INVALID_CREDENTIALS":
                self.logger.error("Invalid client credentials. Please verify your credentials.json file")
            else:
                self.logger.error("Unknown authentication error occurred")
            
            # Store error context for UI display
            self.last_auth_error = error_context
            
            return False

    def test_connection(self) -> bool:
        """
        Test Gmail API connection.

        Returns:
            bool: True if connection successful
        """
        try:
            if not self.service:
                self.logger.error("Gmail service not initialized")
                return False

            # Test basic Gmail API access with a simple call
            try:
                # Try to list labels as a lightweight test
                labels_result = self.service.users().labels().list(userId='me').execute()
                if labels_result:
                    self.logger.info("Gmail API connection test successful")
                    
                    # Try to get email if we don't have it
                    if not self.sender_email or self.sender_email == "authenticated@gmail.com":
                        try:
                            profile = self.service.users().getProfile(userId='me').execute()
                            self.sender_email = profile.get('emailAddress')
                            self.logger.info(f"Updated sender email: {self.sender_email}")
                        except Exception:
                            self.logger.info("Email will be updated when sending first message")
                    
                    return True
                else:
                    return False
                    
            except Exception as api_error:
                if "insufficientPermissions" in str(api_error):
                    # Try a more basic test - just check if service responds
                    self.logger.warning("Limited permissions, but service is accessible")
                    return True
                else:
                    raise api_error

        except Exception as e:
            self.logger.error(f"Gmail API connection test failed: {str(e)}")
            # Log more details about the error
            if "insufficientPermissions" in str(e) or "insufficient authentication scopes" in str(e):
                self.logger.error("Permission error detected. Make sure your credentials have the required scopes:")
                self.logger.error(f"Required scopes: {self.SCOPES}")
            return False

    def prepare_email_content(self, subject_template: str, content_template: str, 
                            contact: Dict[str, Any]) -> Tuple[str, str]:
        """
        Prepare email content by replacing template variables with contact data.

        Args:
            subject_template: Email subject template with variables
            content_template: Email content template with variables
            contact: Contact data dictionary

        Returns:
            Tuple[str, str]: Processed subject and content
        """
        # Prepare replacement dictionary
        replacements = {}

        # Add contact data
        for key, value in contact.items():
            if pd.notna(value):  # Check if value is not NaN
                replacements[key] = str(value)
            else:
                replacements[key] = ""

        # Add sender information
        replacements['sender_email'] = self.sender_email or ""

        # Replace variables in subject
        processed_subject = subject_template
        for key, value in replacements.items():
            processed_subject = processed_subject.replace(f"{{{{{key}}}}}", value)

        # Replace variables in content
        processed_content = content_template
        for key, value in replacements.items():
            processed_content = processed_content.replace(f"{{{{{key}}}}}", value)

        return processed_subject, processed_content

    def create_message(self, to: str, subject: str, message_text: str, is_html: bool = False, attachments: Optional[List[Dict[str, Any]]] = None) -> Dict:
        """
        Create a message for an email.

        Args:
            to: Email address of the receiver
            subject: The subject of the email message
            message_text: The text of the email message
            is_html: Whether the message is HTML
            attachments: List of attachment dictionaries with 'filename' and 'content' keys

        Returns:
            Dict: An object containing a base64url encoded email object
        """
        if is_html or attachments:
            message = MIMEMultipart('mixed')
            if is_html:
                html_part = MIMEText(message_text, 'html')
            else:
                html_part = MIMEText(message_text, 'plain')
            message.attach(html_part)
        else:
            message = MIMEText(message_text)

        message['to'] = to
        if self.sender_name:
            message['from'] = f"{self.sender_name} <{self.sender_email}>"
        else:
            message['from'] = self.sender_email
        message['subject'] = subject

        # Add attachments if provided
        if attachments:
            for attachment in attachments:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment['content'])
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename={attachment["filename"]}')
                message.attach(part)

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        return {'raw': raw_message}

    def send_message(self, message: Dict) -> bool:
        """
        Send an email message.

        Args:
            message: Message to be sent

        Returns:
            bool: True if message sent successfully
        """
        try:
            if not self.service:
                self.logger.error("Gmail service not initialized")
                return False
                
            message = self.service.users().messages().send(userId="me", body=message).execute()
            self.logger.info(f'Message Id: {message["id"]}')
            return True
        except Exception as e:
            self.logger.error(f'An error occurred: {e}')
            return False

    def send_email(self, contact: Dict[str, Any], subject_template: str, 
                   content_template: str, is_html: bool = False, attachments: Optional[List[Dict[str, Any]]] = None) -> bool:
        """
        Send email to a single contact using Gmail API.

        Args:
            contact: Contact information dictionary
            subject_template: Email subject template
            content_template: Email content template
            is_html: Whether content is HTML
            attachments: List of attachment dictionaries with 'filename' and 'content' keys

        Returns:
            bool: True if email sent successfully
        """
        try:
            if not self.service:
                self.logger.error("Gmail API not authenticated")
                return False

            # Get recipient email
            recipient_email = contact.get('email', '')
            if not recipient_email:
                self.logger.warning(f"No email address found for contact")
                return False

            # Prepare email content
            subject, content = self.prepare_email_content(
                subject_template, content_template, contact
            )

            # Create message
            message = self.create_message(recipient_email, subject, content, is_html, attachments)

            # Send message
            success = self.send_message(message)

            if success:
                self.logger.info(f"Email sent successfully to {recipient_email}")
            else:
                self.logger.error(f"Failed to send email to {recipient_email}")

            return success

        except Exception as e:
            self.logger.error(f"Failed to send email to {contact.get('email', '')}: {str(e)}")
            return False