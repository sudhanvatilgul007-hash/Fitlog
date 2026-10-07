from pathlib import Path
from collections.abc import Mapping
from sqlalchemy.engine import URL, make_url


def is_railway(env: Mapping[str, str]) -> bool:
    return bool(env.get('RAILWAY_ENVIRONMENT_ID') or env.get('RAILWAY_PROJECT_ID'))


def database_url(env: Mapping[str, str], backend_dir: Path) -> URL:
    """Resolve local SQLite paths consistently and require durable Railway storage."""
    railway = is_railway(env)
    mount = env.get('RAILWAY_VOLUME_MOUNT_PATH')
    raw = env.get('DATABASE_URL')
    if not raw:
        if railway and not mount:
            raise RuntimeError('Set DATABASE_URL to PostgreSQL, or attach a Railway volume at /data and set DATABASE_URL=sqlite:////data/fitlog.db.')
        raw = f'sqlite:///{Path(mount) / "fitlog.db"}' if railway else 'sqlite:///./fitlog.db'
    url = make_url(raw)
    if url.drivername in ('postgres', 'postgresql'):
        return url.set(drivername='postgresql+psycopg')
    if url.get_backend_name() != 'sqlite':
        return url
    if not url.database or url.database == ':memory:':
        if railway:
            raise RuntimeError('Railway requires a persistent database; SQLite memory databases are not supported.')
        return url
    if url.query.get('uri') == 'true':
        if railway:
            raise RuntimeError('Use a SQLite file on the Railway volume, or PostgreSQL; SQLite URI databases are not supported on Railway.')
        return url
    path = Path(url.database).expanduser()
    if not path.is_absolute():
        path = backend_dir / path
    path = path.resolve()
    if railway:
        if not mount or not path.is_relative_to(Path(mount).resolve()):
            raise RuntimeError('Railway SQLite DATABASE_URL must point inside an attached volume. Mount it at /data and set DATABASE_URL=sqlite:////data/fitlog.db; do not use a local /Users/... path.')
        if not Path(mount).is_dir():
            raise RuntimeError('The configured Railway volume is not mounted. Attach the volume before starting migrations.')
    path.parent.mkdir(parents=True, exist_ok=True)
    return url.set(database=str(path))
