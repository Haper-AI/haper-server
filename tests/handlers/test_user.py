from .conftest import client

def test_request_user_signup_by_credential_success(client):
    response = client.post('/api/v1/user/signup', json={
        'provider': 'credential',
        'email': 'sample@gmail.com',
        'password': 'ComplexP@ssw0rd123!',
    })
    print(response.get_json())
    assert response.status_code == 200
    assert response.json['data']['user'] is not None
