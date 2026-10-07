import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .database_config import database_url, is_railway

backend_dir = Path(__file__).resolve().parent.parent
# Local credentials must never override or supplement Railway configuration.
if not is_railway(os.environ):
    load_dotenv(backend_dir / '.env', override=False)
url = database_url(os.environ, backend_dir)
engine = create_engine(url, connect_args={'check_same_thread': False} if url.get_backend_name() == 'sqlite' else {})
Session = sessionmaker(engine, expire_on_commit=False)
class Base(DeclarativeBase):
    pass
