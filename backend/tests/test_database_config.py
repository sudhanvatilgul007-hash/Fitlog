import os
import subprocess
import sys
from pathlib import Path
import pytest
from sqlalchemy import create_engine, text
from app.database_config import database_url


def test_nested_sqlite_directory_is_created_and_connected(tmp_path):
    url = database_url({'DATABASE_URL': 'sqlite:///data/nested/fitlog.db'}, tmp_path)
    with create_engine(url).begin() as connection:
        connection.execute(text('create table example (id integer)'))
    assert (tmp_path / 'data/nested/fitlog.db').is_file()


def test_railway_rejects_mac_path_without_creating_it(tmp_path):
    with pytest.raises(RuntimeError, match='attached volume'):
        database_url({'RAILWAY_PROJECT_ID': 'test', 'DATABASE_URL': 'sqlite:////Users/example/fitlog.db', 'RAILWAY_VOLUME_MOUNT_PATH': str(tmp_path)}, tmp_path)


def test_railway_requires_storage(tmp_path):
    with pytest.raises(RuntimeError, match='attach a Railway volume'):
        database_url({'RAILWAY_PROJECT_ID': 'test'}, tmp_path)


def test_railway_defaults_to_attached_volume(tmp_path):
    url = database_url({'RAILWAY_PROJECT_ID': 'test', 'RAILWAY_VOLUME_MOUNT_PATH': str(tmp_path)}, Path('/app'))
    assert url.database == str(tmp_path / 'fitlog.db')


def test_railway_rejects_missing_mount(tmp_path):
    mount = tmp_path / 'missing'
    with pytest.raises(RuntimeError, match='not mounted'):
        database_url({'RAILWAY_PROJECT_ID': 'test', 'RAILWAY_VOLUME_MOUNT_PATH': str(mount)}, Path('/app'))
    assert not mount.exists()


@pytest.mark.parametrize('scheme', ['postgres', 'postgresql'])
def test_postgres_keeps_credentials_and_uses_psycopg(scheme, tmp_path):
    url = database_url({'DATABASE_URL': f'{scheme}://user:pass@host/db'}, tmp_path)
    assert url.drivername == 'postgresql+psycopg'
    assert url.password == 'pass'


def test_local_memory_database(tmp_path):
    assert database_url({'DATABASE_URL': 'sqlite:///:memory:'}, tmp_path).database == ':memory:'


def test_migrations_start_with_empty_volume_and_ignore_local_dotenv(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    env = {**os.environ, 'RAILWAY_PROJECT_ID': 'test', 'RAILWAY_VOLUME_MOUNT_PATH': str(tmp_path)}
    env.pop('DATABASE_URL', None)
    result = subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=backend, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    with create_engine(f'sqlite:///{tmp_path / "fitlog.db"}').connect() as connection:
        assert connection.execute(text('select version_num from alembic_version')).scalar() == '0003'
