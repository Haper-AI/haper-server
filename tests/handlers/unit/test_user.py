from .conftest import *

def test_request_user_signup_by_credential_success(client):
    response = client.post('/api/v1/user/signup', json={
        'provider': 'credential',
        'email': 'sample@gmail.com',
        'password': 'ComplexP@ssw0rd123!',
    })
    assert response.status_code == 200
    assert response.json['data']['user'] is not None
    assert response.json['data']['user']['id'] is not None
    assert response.json['data']['user']['email'] == 'sample@gmail.com'
    assert response.json['data']['user']['email_verified'] is False


def test_request_user_signup_by_oauth_success(client):
    response = client.post('/api/v1/user/signup', json={
        'provider': 'google',
        'email': 'sample2@gmail.com',
        'password': 'ComplexP@ssw0rd123!',
        'provider_account_id': 'google_1234567890',
        'access_token': 'google_access_token',
        'refresh_token': 'google_refresh_token',
        'expires_at': 1677723200,
        'name': 'google_name',
        'image': 'https://www.tests-haper.com/images/sample.png',
    })
    assert response.status_code == 200
    assert response.json['data']['user'] is not None
    assert response.json['data']['user']['id'] is not None
    assert response.json['data']['user']['email'] == 'sample2@gmail.com'
    assert response.json['data']['user']['email_verified'] is True