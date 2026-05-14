import sqlite3
import os
import json
from bson import ObjectId

class SQLiteDB:
    is_sqlite = True
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS campaigns 
                     (id TEXT PRIMARY KEY, data TEXT)''')
        conn.commit()
        conn.close()

    @property
    def campaigns(self):
        return self

    def insert_one(self, data):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        if '_id' not in data:
            data['_id'] = str(ObjectId())
        campaign_id = str(data['_id'])
        c.execute("INSERT INTO campaigns (id, data) VALUES (?, ?)", (campaign_id, json.dumps(data)))
        conn.commit()
        conn.close()
        class Result:
            def __init__(self, id): self.inserted_id = id
        return Result(campaign_id)

    def find(self, query=None):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT data FROM campaigns")
        rows = c.fetchall()
        conn.close()
        self._data = [json.loads(r[0]) for r in rows]
        return self

    def __iter__(self):
        # Allow casting to list: list(db.campaigns.find())
        return iter(getattr(self, '_data', []))

    def sort(self, field, direction):
        if not hasattr(self, '_data'):
            self.find()
        reverse = True if direction == -1 else False
        self._data.sort(key=lambda x: x.get(field, 0), reverse=reverse)
        return self

    def find_one(self, query):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        campaign_id = str(query.get('_id'))
        c.execute("SELECT data FROM campaigns WHERE id = ?", (campaign_id,))
        row = c.fetchone()
        conn.close()
        return json.loads(row[0]) if row else None

    def update_one(self, query, update):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        campaign_id = str(query.get('_id'))
        
        # Simple update logic for mock
        current = self.find_one(query)
        if current:
            if '$set' in update:
                current.update(update['$set'])
            if '$addToSet' in update:
                for key, val in update['$addToSet'].items():
                    if key not in current: current[key] = []
                    if val not in current[key]: current[key].append(val)
            
            c.execute("UPDATE campaigns SET data = ? WHERE id = ?", (json.dumps(current), campaign_id))
        conn.commit()
        conn.close()
