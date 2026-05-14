import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'bulkmail-secret-key')
    # Default to localhost if MONGO_URI is not set
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/bulkmail_pro')
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'app', 'static', 'uploads')
    if os.getenv('VERCEL'):
        UPLOAD_FOLDER = '/tmp'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
    
    # SMTP Settings
    SMTP_SERVER = os.getenv('SMTP_SERVER')
    SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
    SMTP_USERNAME = os.getenv('SMTP_USERNAME')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
    
    # API Settings (Brevo/SendGrid)
    BREVO_API_KEY = os.getenv('BREVO_API_KEY')
    SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
    
    # Base URL for tracking pixels
    BASE_URL = os.getenv('BASE_URL', 'http://127.0.0.1:5000')
