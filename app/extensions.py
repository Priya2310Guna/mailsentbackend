from flask_socketio import SocketIO
from apscheduler.schedulers.background import BackgroundScheduler

socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')
scheduler = BackgroundScheduler()
db = None
