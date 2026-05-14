import smtplib
import time
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from jinja2 import Template
import requests
from functools import wraps

def retry(exceptions, tries=3, delay=1, backoff=2):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                success, msg = f(*args, **kwargs)
                if success:
                    return True, msg
                time.sleep(mdelay)
                mtries -= 1
                mdelay *= backoff
            return f(*args, **kwargs)
        return wrapper
    return decorator

class MailService:
    def __init__(self, config):
        self.config = config

    def check_connection(self):
        try:
            if not self.config.get('SMTP_SERVER') or not self.config.get('SMTP_USERNAME'):
                return False, "SMTP configuration missing"
            
            server = smtplib.SMTP(self.config['SMTP_SERVER'], self.config['SMTP_PORT'], timeout=5)
            server.starttls()
            server.login(self.config['SMTP_USERNAME'], self.config['SMTP_PASSWORD'])
            server.quit()
            return True, "Connection Successful"
        except Exception as e:
            return False, str(e)

    def send_via_smtp(self, recipient_email, subject, body, attachments=None):
        try:
            msg = MIMEMultipart()
            msg['From'] = self.config['SMTP_USERNAME']
            msg['To'] = recipient_email
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'html'))
            
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as attachment:
                            part = MIMEBase("application", "octet-stream")
                            part.set_payload(attachment.read())
                            encoders.encode_base64(part)
                            part.add_header(
                                "Content-Disposition",
                                f"attachment; filename= {os.path.basename(file_path)}",
                            )
                            msg.attach(part)

            server = smtplib.SMTP(self.config['SMTP_SERVER'], self.config['SMTP_PORT'])
            server.starttls()
            server.login(self.config['SMTP_USERNAME'], self.config['SMTP_PASSWORD'])
            server.send_message(msg)
            server.quit()
            return True, "Sent"
        except Exception as e:
            return False, str(e)

    @retry(Exception, tries=3)
    def send_via_brevo(self, recipient_email, subject, body, attachments=None):
        # Implementation for Brevo API
        url = "https://api.brevo.com/v3/smtp/email"
        if not self.config.get('BREVO_API_KEY'):
            return False, "Brevo API key missing"
            
        headers = {
            "api-key": self.config['BREVO_API_KEY'],
            "Content-Type": "application/json"
        }
        payload = {
            "sender": {"email": self.config['SMTP_USERNAME']},
            "to": [{"email": recipient_email}],
            "subject": subject,
            "htmlContent": body
        }
        # Add attachment logic for Brevo if needed
        try:
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 201:
                return True, "Sent"
            return False, response.text
        except Exception as e:
            return False, str(e)

    def process_campaign(self, campaign_id, recipients, subject_template, body_template, delay=2, provider='smtp'):
        from app.extensions import socketio, db
        from bson import ObjectId
        
        total = len(recipients)
        sent = 0
        failed = 0
        
        db.campaigns.update_one({'_id': ObjectId(campaign_id)}, {'$set': {'status': 'processing'}})
        
        for index, recipient in enumerate(recipients):
            # Personalization
            name = recipient.get('name', 'User')
            email = recipient.get('email')
            
            if not email:
                continue
                
            personalized_subject = Template(subject_template).render(name=name)
            
            # Inject tracking pixel
            base_url = self.config.get('BASE_URL', 'http://127.0.0.1:5000')
            tracking_pixel = f'<img src="{base_url}/api/campaigns/track/{campaign_id}/{email}" width="1" height="1" />'
            personalized_body = Template(body_template).render(name=name) + tracking_pixel
            
            success, message = (True, "Sent")
            if provider == 'smtp':
                success, message = self.send_via_smtp(email, personalized_subject, personalized_body)
            elif provider == 'brevo':
                success, message = self.send_via_brevo(email, personalized_subject, personalized_body)
            
            if success:
                sent += 1
            else:
                failed += 1
            
            # Update stats
            progress = int(((index + 1) / total) * 100)
            socketio.emit('campaign_progress', {
                'campaign_id': str(campaign_id),
                'progress': progress,
                'sent': sent,
                'failed': failed
            })
            
            # Anti-spam delay
            time.sleep(delay)
            
        db.campaigns.update_one({'_id': ObjectId(campaign_id)}, {
            '$set': {
                'status': 'completed',
                'sent_count': sent,
                'failed_count': failed,
                'completed_at': time.time()
            }
        })
        socketio.emit('campaign_completed', {'campaign_id': str(campaign_id)})
