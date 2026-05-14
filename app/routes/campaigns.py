from flask import Blueprint, request, jsonify
from app import extensions as ext
from app.extensions import scheduler
from app.services.mail_service import MailService
from config import Config
import pandas as pd
import os
from bson import ObjectId
import threading
from datetime import datetime

campaign_bp = Blueprint('campaigns', __name__)
mail_service = MailService(Config.__dict__)

@campaign_bp.route('/create', methods=['POST'])
def create_campaign():
    data = request.form
    recipients_file = request.files.get('recipients')
    attachments = request.files.getlist('attachments')
    scheduled_at_str = data.get('scheduled_at')
    
    if not recipients_file:
        return jsonify({'error': 'Recipients file is required'}), 400
        
    # Save file and parse recipients
    file_path = os.path.join(Config.UPLOAD_FOLDER, recipients_file.filename)
    recipients_file.save(file_path)
    
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path)
    
    recipients = df.to_dict('records')
    
    # Save attachments
    attachment_paths = []
    for att in attachments:
        path = os.path.join(Config.UPLOAD_FOLDER, att.filename)
        att.save(path)
        attachment_paths.append(path)
    
    campaign = {
        'name': data.get('name'),
        'subject': data.get('subject'),
        'body': data.get('body'),
        'recipients_count': len(recipients),
        'status': 'pending',
        'created_at': datetime.now().timestamp(),
        'provider': data.get('provider', 'smtp'),
        'delay': int(data.get('delay', 2)),
        'scheduled_at': scheduled_at_str
    }
    
    result = ext.db.campaigns.insert_one(campaign)
    campaign_id = str(result.inserted_id)
    
    # Scheduling logic
    if scheduled_at_str:
        try:
            # Handle ISO format from frontend (e.g., 2024-05-14T15:30)
            run_date = datetime.fromisoformat(scheduled_at_str.replace('Z', '+00:00'))
            
            if run_date > datetime.now():
                scheduler.add_job(
                    id=campaign_id,
                    func=mail_service.process_campaign,
                    trigger='date',
                    run_date=run_date,
                    args=(campaign_id, recipients, campaign['subject'], campaign['body'], campaign['delay'], campaign['provider'])
                )
                ext.db.campaigns.update_one({'_id': ObjectId(campaign_id)}, {'$set': {'status': 'scheduled'}})
                return jsonify({'message': 'Campaign scheduled', 'campaign_id': campaign_id}), 201
        except Exception as e:
            print(f"Scheduling error: {e}")
            # Fallback to immediate if scheduling fails
            pass

    # Start processing in background immediately
    thread = threading.Thread(
        target=mail_service.process_campaign,
        args=(campaign_id, recipients, campaign['subject'], campaign['body'], campaign['delay'], campaign['provider'])
    )
    thread.start()
    
    return jsonify({'message': 'Campaign started', 'campaign_id': campaign_id}), 201

@campaign_bp.route('/track/<campaign_id>/<email>', methods=['GET'])
def track_open(campaign_id, email):
    ext.db.campaigns.update_one(
        {'_id': ObjectId(campaign_id)},
        {'$addToSet': {'opened_by': email}}
    )
    # Return a 1x1 transparent pixel
    pixel = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
    return pixel, 200, {'Content-Type': 'image/gif'}

@campaign_bp.route('/stats', methods=['GET'])
def get_stats():
    campaigns = list(ext.db.campaigns.find().sort('created_at', -1))
    for c in campaigns:
        c['_id'] = str(c['_id'])
    return jsonify(campaigns)
