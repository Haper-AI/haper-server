from .conftest import *
from tests import generate_random_string


class TestUserSignupLogin:
    class TestSuccess:
        def test_success_by_credential(self, client):
            email = f'{generate_random_string(8)}@gmail.com'
            response = client.post('/api/v1/user/signup', json={
                'provider': 'credential',
                'email': email,
                'password': 'ComplexP@ssw0rd123!',
            })
            assert response.status_code == 200

            response = client.post('/api/v1/user/login', json={
                'provider': 'credential',
                'email': email,
                'password': 'ComplexP@ssw0rd123!',
            })
            assert response.status_code == 200

        def test_success_by_oauth(self, client):
            email = f'{generate_random_string(8)}@gmail.com'
            provider_account_id = f'google_{generate_random_string(16)}'
            response = client.post('/api/v1/user/signup', json={
                'provider': 'google',
                'email': email,
                'password': 'ComplexP@ssw0rd123!',
                'provider_account_id': provider_account_id,
                'access_token': 'google_access_token',
                'refresh_token': 'google_refresh_token',
                'expires_at': 1677723200,
            })
            assert response.status_code == 200

            response = client.post('/api/v1/user/login', json={
                'provider': 'google',
                'email': email,
                'provider_account_id': provider_account_id,
                'access_token': 'google_access_token',
            })
            assert response.status_code == 200

    class TestFail:
        def test_fail_by_wrong_login_method(self, client):
            email = f'{generate_random_string(8)}@gmail.com'
            provider_account_id = f'google_{generate_random_string(16)}'
            # sign up by credential while login in by oauth
            response = client.post('/api/v1/user/signup', json={
                'provider': 'credential',
                'email': email,
                'password': 'ComplexP@ssw0rd123!',
            })
            assert response.status_code == 200

            response = client.post('/api/v1/user/login', json={
                'provider': 'google',
                'email': email,
                'provider_account_id': provider_account_id,
                'access_token': 'google_access_token',
            })
            assert response.status_code == 400

            email = f'{generate_random_string(8)}@gmail.com'
            provider_account_id = f'google_{generate_random_string(16)}'
            # sign up by oauth while login in by credential
            response = client.post('/api/v1/user/signup', json={
                'provider': 'google',
                'email': email,
                'password': 'ComplexP@ssw0rd123!',
                'provider_account_id': provider_account_id,
                'access_token': 'google_access_token',
                'refresh_token': 'google_refresh_token',
                'expires_at': 1677723200,
            })
            assert response.status_code == 200

            response = client.post('/api/v1/user/login', json={
                'provider': 'credential',
                'email': email,
                'password': 'ComplexP@ssw0rd123!',
            })
            assert response.status_code == 400
