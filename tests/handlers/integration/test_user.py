from .conftest import *

def test_request_user_signup_by_credential_login_success(client):
    response = client.post('/api/v1/user/signup', json={
        'provider': 'credential',
        'email': 'sample@gmail.com',
        'password': 'ComplexP@ssw0rd123!',
    })
    assert response.status_code == 200

    response = client.post('/api/v1/user/login', json={
        'provider': 'credential',
        'email': 'sample@gmail.com',
        'password': 'ComplexP@ssw0rd123!',
    })
    assert response.status_code == 200