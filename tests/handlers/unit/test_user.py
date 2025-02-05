from .conftest import *
from biz.utils.response import ResponseCode
from tests import generate_random_string

class TestUserSignupByCredential:
    def test_success(self, client):
        email = f'{generate_random_string(8)}@gmail.com'
        response = client.post('/api/v1/user/signup', json={
            'provider': 'credential',
            'email': email,
            'password': 'ComplexP@ssw0rd123!',
        })
        assert response.status_code == 200
        assert response.json['status'] == ResponseCode.SUCCESS.value
        assert response.json['data']['user'] is not None
        assert response.json['data']['user']['id'] is not None
        assert response.json['data']['user']['email'] == email
        assert response.json['data']['user']['email_verified'] is False

    class TestFail:
        def test_fail_by_invalid_email(self, client):
            response = client.post('/api/v1/user/signup', json={
                'provider': 'credential',
                'email': 'sample',
                'password': 'ComplexP@ssw0rd123!',
            })
            assert response.status_code == 400
            assert response.json['status'] == ResponseCode.InvalidParam.value

        def test_fail_by_invalid_password(self, client):
            email = f'{generate_random_string(8)}@gmail.com'
            response = client.post('/api/v1/user/signup', json={
                'provider': 'credential',
                'email': email,
                'password': 'ComplexPassword',
            })
            assert response.status_code == 400
            assert response.json['status'] == ResponseCode.InvalidParam.value


class TestUserSignupByOauth:
    def test_success(self, client):
        email = f'{generate_random_string(8)}@gmail.com'
        provider_account_id = f'google_{generate_random_string(16)}'
        response = client.post('/api/v1/user/signup', json={
            'provider': 'google',
            'email': email,
            'provider_account_id': provider_account_id,
            'access_token': 'google_access_token',
            'refresh_token': 'google_refresh_token',
            'expires_at': 1677723200,
            'name': 'google_name',
            'image': 'https://www.tests-haper.com/images/sample.png',
        })
        assert response.status_code == 200
        assert response.json['status'] == ResponseCode.SUCCESS.value
        assert response.json['data']['user'] is not None
        assert response.json['data']['user']['id'] is not None
        assert response.json['data']['user']['email'] == email
        assert response.json['data']['user']['email_verified'] is True

    class TestFail:
        def test_fail_by_invalid_email(self, client):
            response = client.post('/api/v1/user/signup', json={
                'provider': 'google',
                'email': 'sample',
                'provider_account_id': 'google_1234567890',
                'access_token': 'google_access_token',
                'refresh_token': 'google_refresh_token',
                'expires_at': 1677723200,
            })
            assert response.status_code == 400
            assert response.json['status'] == ResponseCode.InvalidParam.value

        def test_fail_by_missing_provider_id(self, client):
            email = f'{generate_random_string(8)}@gmail.com'
            response = client.post('/api/v1/user/signup', json={
                'provider': 'google',
                'email': email,
                'password': 'ComplexP@ssw0rd123!',
                'access_token': 'google_access_token',
                'refresh_token': 'google_refresh_token',
            })
            assert response.status_code == 400
            assert response.json['status'] == ResponseCode.InvalidParam.value

        def test_fail_by_missing_access_token(self, client):
            email = f'{generate_random_string(8)}@gmail.com'
            provider_account_id = f'google_{generate_random_string(16)}'
            response = client.post('/api/v1/user/signup', json={
                'provider': 'google',
                'email': email,
                'provider_account_id': provider_account_id,
                'refresh_token': 'google_refresh_token',
            })
            assert response.status_code == 400
            assert response.json['status'] == ResponseCode.InvalidParam.value