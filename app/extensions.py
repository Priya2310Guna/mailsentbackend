from flask_socketio import SocketIO
from apscheduler.schedulers.background import BackgroundScheduler

socketio = SocketIO(cors_allowed_origins="*", async_mode='eventlet')
scheduler = BackgroundScheduler()
db = None
