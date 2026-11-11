"""Namespaced user-data storage outside replaceable module folders."""
import json
import re
import sqlite3
from pathlib import Path

class NamespaceStorage:
    def __init__(self, base:Path, namespace:str):
        if not re.fullmatch(r'hj\.[a-z][a-z0-9_]{1,50}',namespace):
            raise ValueError('Invalid module namespace')
        self.path=base/(namespace+'.sqlite3')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.db() as con:
            con.execute('CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, content TEXT NOT NULL)')
    def db(self):return sqlite3.connect(self.path,timeout=10)
    def get(self,key,default=None):
        with self.db() as con:
            row=con.execute('SELECT content FROM kv WHERE key=?',(key,)).fetchone()
        return json.loads(row[0]) if row else default
    def set(self,key,value):
        payload=json.dumps(value,ensure_ascii=False)
        with self.db() as con:
            con.execute('INSERT OR REPLACE INTO kv(key,content) VALUES (?,?)',(key,payload))
    def delete(self,key):
        with self.db() as con:con.execute('DELETE FROM kv WHERE key=?',(key,))
