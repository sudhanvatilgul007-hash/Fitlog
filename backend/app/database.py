import os
from pathlib import Path
from dotenv import load_dotenv

# Load only the backend's local file; deployed environment variables win.
load_dotenv(Path(__file__).resolve().parent.parent / '.env', override=False)
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

url = os.getenv('DATABASE_URL', 'sqlite:///./fitlog.db')
if url.startswith('postgres://'):
    url = url.replace('postgres://', 'postgresql+psycopg://', 1)
elif url.startswith('postgresql://'):
    url = url.replace('postgresql://', 'postgresql+psycopg://', 1)
engine = create_engine(url, connect_args={'check_same_thread': False} if url.startswith('sqlite') else {})
Session = sessionmaker(engine, expire_on_commit=False)
class Base(DeclarativeBase):
    pass
