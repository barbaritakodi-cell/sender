import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import re
import logging
import pandas as pd
from typing import Dict, Any, Tuple, List, Optional

class EmailSender:
    def __init__(self, smtp_server: str, smtp_port: int, use_tls: bool, 
                 sender_email: str, sender_password: str, sender_name: str = "", use_ssl: bool = False, reply_to_email: str = ""):
        """
        Initialize the EmailSender with SMTP configuration.
        
        Args:
            smtp_server: SMTP server address
            smtp_port: SMTP server port
            use_tls: Whether to use STARTTLS encryption
            sender_email: Sender's email address
            sender_password: Sender's password or app password
            sender_name: Display name for sender
            use_ssl: Whether to use SSL encryption (port 465)
            reply_to_email: Email address for replies (defaults to sender_email if empty)
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.sender_name = sender_name
        self.reply_to_email = reply_to_email if reply_to_email else sender_email
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def test_connection(self) -> bool:
        """
        Test SMTP connection with current settings.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            context = ssl.create_default_context()
            
            if self.use_ssl:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context)
            elif self.use_tls:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls(context=context)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            
            server.login(self.sender_email, self.sender_password)
            server.quit()
            
            self.logger.info("SMTP connection test successful")
            return True
            
        except Exception as e:
            self.logger.error(f"SMTP connection test failed: {str(e)}")
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
        replacements['sender_name'] = self.sender_name
        replacements['sender_email'] = self.sender_email
        
        # Replace variables in subject
        processed_subject = subject_template
        for key, value in replacements.items():
            processed_subject = processed_subject.replace(f"{{{{{key}}}}}", value)
        
        # Replace variables in content
        processed_content = content_template
        for key, value in replacements.items():
            processed_content = processed_content.replace(f"{{{{{key}}}}}", value)
        
        return processed_subject, processed_content
    
    def create_email_message(self, recipient_email: str, subject: str, 
                           content: str, is_html: bool = False, attachments: Optional[List[Dict[str, Any]]] = None) -> MIMEMultipart:
        """
        Create email message with proper headers and content.
        
        Args:
            recipient_email: Recipient's email address
            subject: Email subject
            content: Email content
            is_html: Whether content is HTML
            attachments: List of attachment dictionaries with 'filename' and 'content' keys
            
        Returns:
            MIMEMultipart: Configured email message
        """
        from email.utils import formataddr
        
        message = MIMEMultipart("mixed")
        
        # Set headers - Use formataddr for proper RFC compliance (important for TurboSMTP)
        if self.sender_name:
            message["From"] = formataddr((self.sender_name, self.sender_email))
        else:
            message["From"] = self.sender_email
        
        message["To"] = recipient_email
        message["Subject"] = subject
        message["Reply-To"] = self.reply_to_email
        
        # Add content
        if is_html:
            html_part = MIMEText(content, "html", "utf-8")
            message.attach(html_part)
        else:
            text_part = MIMEText(content, "plain", "utf-8")
            message.attach(text_part)
        
        # Add attachments if provided
        if attachments:
            for attachment in attachments:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment['content'])
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename={attachment["filename"]}')
                message.attach(part)
        
        return message
    
    def send_email(self, contact: Dict[str, Any], subject_template: str, 
                   content_template: str, is_html: bool = False, attachments: Optional[List[Dict[str, Any]]] = None) -> bool:
        """
        Send email to a single contact.
        
        Args:
            contact: Contact information dictionary
            subject_template: Email subject template
            content_template: Email content template
            is_html: Whether content is HTML
            attachments: List of attachment dictionaries with 'filename' and 'content' keys
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Get recipient email
            recipient_email = contact.get('email', '')
            if not recipient_email or not self._is_valid_email(recipient_email):
                self.logger.warning(f"Invalid email address: {recipient_email}")
                return False
            
            # Prepare email content
            subject, content = self.prepare_email_content(
                subject_template, content_template, contact
            )
            
            # Create email message
            message = self.create_email_message(
                recipient_email, subject, content, is_html, attachments
            )
            
            # Send email
            context = ssl.create_default_context()
            
            if self.use_ssl:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context)
            elif self.use_tls:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls(context=context)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            
            server.login(self.sender_email, self.sender_password)
            server.send_message(message)
            server.quit()
            
            self.logger.info(f"Email sent successfully to {recipient_email}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            self.logger.error(f"SMTP Authentication failed: {str(e)}")
            return False
        except smtplib.SMTPRecipientsRefused as e:
            self.logger.error(f"Recipient refused: {str(e)}")
            return False
        except smtplib.SMTPServerDisconnected as e:
            self.logger.error(f"SMTP server disconnected: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to send email to {contact.get('email', '')}: {str(e)}")
            return False
    
    def _is_valid_email(self, email: str) -> bool:
        """
        Validate email address format.
        
        Args:
            email: Email address to validate
            
        Returns:
            bool: True if email is valid, False otherwise
        """
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def send_bulk_emails(self, contacts_df, subject_template: str, 
                        content_template: str, is_html: bool = False, 
                        delay: float = 1.0) -> Dict[str, Any]:
        """
        Send emails to multiple contacts.
        
        Args:
            contacts_df: DataFrame containing contact information
            subject_template: Email subject template
            content_template: Email content template
            is_html: Whether content is HTML
            delay: Delay between emails in seconds
            
        Returns:
            Dict[str, Any]: Sending results summary
        """
        import time
        import pandas as pd
        
        results = {
            'total': len(contacts_df),
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        for index, contact in contacts_df.iterrows():
            try:
                success = self.send_email(contact, subject_template, content_template, is_html)
                
                if success:
                    results['success'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append({
                        'email': contact.get('email', ''),
                        'error': 'Failed to send email'
                    })
                
                # Add delay between emails
                if delay > 0:
                    time.sleep(delay)
                    
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'email': contact.get('email', ''),
                    'error': str(e)
                })
        
        return results
