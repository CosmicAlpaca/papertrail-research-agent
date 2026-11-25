import hashlib
import time
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, String, JSON, Float
from sqlalchemy.orm import declarative_base, sessionmaker
from server.config import ROOT, settings

(ROOT / 'work').mkdir(exist_ok=True)
database_url = settings.database_url
if database_url.startswith('postgres://'): database_url = database_url.replace('postgres://', 'postgresql+psycopg://', 1)
elif database_url.startswith('postgresql://'): database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
engine = create_engine(database_url, connect_args={'check_same_thread': False, 'timeout': 30} if database_url.startswith('sqlite') else {}, pool_pre_ping=True)
Session = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()

def now():
    return datetime.now(timezone.utc).isoformat()

class Workspace(Base):
    __tablename__ = 'workspaces'
    id = Column(String, primary_key=True)
    token_hash = Column(String, unique=True, nullable=False)
    created_at = Column(String, default=now)

class Run(Base):
    __tablename__ = 'runs'
    id = Column(String, primary_key=True)
    workspace_id = Column(String, index=True, nullable=False)
    created_at = Column(String, default=now)
    status = Column(String, default='queued')
    request = Column(JSON, default=dict)
    result = Column(JSON, default=dict)
    events = Column(JSON, default=list)
    feedback = Column(JSON, default=dict)

class Cache(Base):
    __tablename__ = 'api_cache'
    key = Column(String, primary_key=True)
    created_at = Column(Float, default=time.time)
    payload = Column(JSON)

def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()

def update_run(run_id, **values):
    with Session() as db:
        row = db.get(Run, run_id)
        if row:
            for key, value in values.items():
                setattr(row, key, value)
            db.commit()

def event(run_id, step, message, **detail):
    with Session() as db:
        row = db.get(Run, run_id)
        if row:
            row.events = [*(row.events or []), {'at': now(), 'step': step, 'message': message, **detail}]
            db.commit()
