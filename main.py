import eventlet
eventlet.monkey_patch()

import os
from flask import Flask, jsonify
from flask_cors import CORS
from app.extensions import socketio
import app.extensions as ext
from pymongo import MongoClient
from config import Config

# Initialize extensions
db_client = None
fallback_active = False

def create_app():
    global db, db_client, fallback_active
    app = Flask(__name__)
    app.config.from_object(Config)
    
    CORS(app, resources={r"/*": {"origins": "*"}})
    socketio.init_app(app)
    
    if not ext.scheduler.running:
        ext.scheduler.start()
    
    @app.errorhandler(Exception)
    def handle_exception(e):
        # Pass through HTTP errors
        if hasattr(e, 'code'):
            return jsonify(error=str(e)), e.code
        # Handle non-HTTP errors
        print(f"Unhandled Exception: {e}")
        return jsonify(error="Internal Server Error"), 500
    
    try:
        db_client = MongoClient(app.config['MONGO_URI'], serverSelectionTimeoutMS=2000)
        db_client.server_info()
        ext.db = db_client.get_database()
        fallback_active = False
        print("MongoDB connected successfully")
    except Exception as e:
        print(f"MongoDB connection failed: {e}")
        print("Switching to local SQLite fallback...")
        from app.mock_db import SQLiteDB
        ext.db = SQLiteDB(os.path.join(app.config['UPLOAD_FOLDER'], 'local_data.db'))
        fallback_active = True
        print("SQLite fallback active")
    
    # Ensure upload directory exists
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    # Register Blueprints
    from app.routes.campaigns import campaign_bp
    app.register_blueprint(campaign_bp, url_prefix='/api/campaigns')
    
    @app.route('/')
    def home():
        return jsonify({
            "message": "Bulk Mail Pro API is Running",
            "status": "online",
            "endpoints": {
                "health": "/health",
                "campaigns": "/api/campaigns/stats"
            }
        })
    
    @app.route('/health')
    def health():
        from app.services.mail_service import MailService
        ms = MailService(app.config)
        smtp_success, smtp_msg = ms.check_connection()
        
        db_status = "connected"
        if fallback_active:
             db_status = "fallback (sqlite)"
        elif ext.db is None:
             db_status = "disconnected"
             
        return {
            "mongodb": db_status,
            "smtp": "connected" if smtp_success else "failed",
            "smtp_error": smtp_msg if not smtp_success else None
        }

    @socketio.on('check_health')
    def handle_check_health():
        res = health()
        socketio.emit('health_status', res)
    
    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"Server running on http://localhost:{port}")
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True, use_reloader=False)
