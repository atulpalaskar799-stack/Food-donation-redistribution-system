import os, pytest
os.environ.setdefault("SECRET_KEY","test")
from app import app

@pytest.fixture()
def client():
    app.config.update(TESTING=True)
    return app.test_client()

def test_home(client):
    r=client.get("/")
    assert r.status_code==200

def test_login_page(client):
    r=client.get("/login")
    assert r.status_code==200

def test_register_page(client):
    r=client.get("/register")
    assert r.status_code==200
