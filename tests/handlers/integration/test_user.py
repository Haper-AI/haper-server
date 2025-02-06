from .conftest import *
from tests import generate_random_string
from unittest.mock import patch


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

            with patch('requests.get') as mock_get:
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = {'email': email}
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

        def test_success_by_credential_with_min_password(self, client):
            email = f'{generate_random_string(8)}@gmail.com'
            response = client.post('/api/v1/user/signup', json={
                'provider': 'credential',
                'email': email,
                'password': 'P@ssw0rd',
            })
            assert response.status_code == 200

            response = client.post('/api/v1/user/login', json={
                'provider': 'credential',
                'email': email,
                'password': 'P@ssw0rd',
            })
            assert response.status_code == 200

        def test_success_with_special_characters_in_email(self, client):
            email = f'{generate_random_string(8)}!#$%&\'*+/=?^_`~@gmail.com'
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

        def test_success_by_oauth_with_missing_optional_fields(self, client):
            email = f'{generate_random_string(8)}@gmail.com'
            provider_account_id = f'google_{generate_random_string(16)}'

            with patch('requests.get') as mock_get:
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = {'email': email}
                response = client.post('/api/v1/user/signup', json={
                    'provider': 'google',
                    'email': email,
                    'provider_account_id': provider_account_id,
                    'access_token': 'google_access_token',
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

            with patch('requests.get') as mock_get:
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = {'email': email}
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
            with patch('requests.get') as mock_get:
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = {'email': email}
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

        def test_fail_by_missing_email_on_signup(self, client):
            response = client.post('/api/v1/user/signup', json={
                'provider': 'credential',
                'password': 'ComplexP@ssw0rd123!',
            })
            assert response.status_code == 400

        def test_fail_by_missing_password_on_signup(self, client):
            email = f'{generate_random_string(8)}@gmail.com'
            response = client.post('/api/v1/user/signup', json={
                'provider': 'credential',
                'email': email,
            })
            assert response.status_code == 400

        def test_fail_by_invalid_email_format(self, client):
            email = f'{generate_random_string(8)}@gmail'
            response = client.post('/api/v1/user/signup', json={
                'provider': 'credential',
                'email': email,
                'password': 'ComplexP@ssw0rd123!',
            })
            assert response.status_code == 400

        def test_fail_by_invalid_oauth_token(self, client):
            email = f'{generate_random_string(8)}@gmail.com'
            provider_account_id = f'google_{generate_random_string(16)}'
            response = client.post('/api/v1/user/signup', json={
                'provider': 'google',
                'email': email,
                'provider_account_id': provider_account_id,
                'access_token': 'invalid_token',
                'refresh_token': 'google_refresh_token',
                'expires_at': 1677723200,
            })
            assert response.status_code == 401

        def test_fail_by_expired_oauth_token(self, client):
            email = f'{generate_random_string(8)}@gmail.com'
            provider_account_id = f'google_{generate_random_string(16)}'
            response = client.post('/api/v1/user/signup', json={
                'provider': 'google',
                'email': email,
                'provider_account_id': provider_account_id,
                'access_token': 'expired_token',
                'refresh_token': 'google_refresh_token',
                'expires_at': 0,
            })
            assert response.status_code == 400