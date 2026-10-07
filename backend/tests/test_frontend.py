import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.frontend import mount_frontend


@pytest.fixture()
def client(tmp_path):
    (tmp_path / 'index.html').write_text('<!doctype html><title>fitlog</title><div id="root"></div>')
    (tmp_path / 'assets').mkdir()
    (tmp_path / 'assets' / 'app.js').write_text('console.log("fitlog");')
    original_routes = list(app.router.routes)
    mount_frontend(app, tmp_path)
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.router.routes[:] = original_routes


def test_frontend_and_api_share_one_origin(client):
    root = client.get('/')
    assert root.status_code == 200
    assert '<title>fitlog</title>' in root.text
    assert root.headers['content-type'].startswith('text/html')
    assert root.headers['cache-control'] == 'no-cache'
    assert client.get('/assets/app.js').status_code == 200
    assert client.get('/api/health').json() == {'status': 'ok', 'app': 'fitlog'}
    assert client.get('/docs').status_code == 200
    assert 'paths' in client.get('/openapi.json').json()


def test_browser_navigation_falls_back_to_frontend(client):
    response = client.get('/history', headers={'Accept': 'text/html'})
    assert response.status_code == 200
    assert '<title>fitlog</title>' in response.text
    assert client.head('/history', headers={'Accept': 'text/html'}).status_code == 200


@pytest.mark.parametrize('path', ['/api/missing', '/assets/missing.js', '/missing.css'])
def test_missing_api_and_assets_remain_404(client, path):
    response = client.get(path, headers={'Accept': 'text/html'})
    assert response.status_code == 404
    assert response.json() == {'detail': 'Not Found'}


def test_non_browser_and_post_requests_do_not_receive_app_shell(client):
    assert client.get('/missing', headers={'Accept': 'application/json'}).status_code == 404
    assert client.post('/history', headers={'Accept': 'text/html'}).status_code == 405


def test_configured_missing_build_fails_clearly(monkeypatch, tmp_path):
    monkeypatch.setenv('FRONTEND_DIST', str(tmp_path / 'missing'))
    with pytest.raises(RuntimeError, match='missing its index.html'):
        mount_frontend(app)
