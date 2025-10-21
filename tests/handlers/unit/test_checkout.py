from unittest.mock import MagicMock

import stripe

from biz.dal.user import User
from biz.dal.user_subscription import UserSubscription, UserSubscriptionStatus
from biz.handler.middleware import gen_jwt_auth
from biz.service.db import get_session
from biz.utils.env import RuntimeEnv


class TestNewCheckoutSession:
    def test_success(self, client, new_user):
        # Mock the Stripe API response
        checkout_session_mock = MagicMock()
        checkout_session_mock.id = 'cs_test_123'
        checkout_session_mock.client_secret = 'cs_test_secret_123'
        stripe.checkout.Session.create = MagicMock(return_value=checkout_session_mock)

        client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(new_user.id)))
        # Simulate a request to the checkout session endpoint
        response = client.post('/api/v1/checkout/session', json={
            'billing_cycle': 'month',
            'return_url': 'https://example.com/success',
        })

        # Assert the response
        assert response.status_code == 200
        assert response.get_json()['data']['checkout_session_id'] == 'cs_test_123'

    class TestFail:
        def test_fail_by_auth_fail(self, client):
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, "")
            response = client.post('/api/v1/checkout/session', json={
                'billing_cycle': 'month',
                'return_url': 'https://example.com/success',
            })
            assert response.status_code == 401

        def test_fail_by_already_subscribed(self, client, new_user):
            with get_session(write=True) as session:
                User.update(session, new_user.id, stripe_customer_id="cus_test_123")
                UserSubscription.add(session, new_user.id, "cus_test_123", "sub_test_123", "month",
                                     UserSubscriptionStatus.Active)

            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(new_user.id)))
            # Simulate a request to the checkout session endpoint
            response = client.post('/api/v1/checkout/session', json={
                'billing_cycle': 'month',
                'return_url': 'https://example.com/success',
            })

            # Assert the response
            assert response.status_code == 400



class TestGetCheckoutSessionStatus:
    def test_success(self, client, new_user):
        # Mock the Stripe API response
        checkout_session_mock = MagicMock()
        checkout_session_mock.status = "active"
        checkout_session_mock.customer_details.email = new_user.email

        stripe.checkout.Session.retrieve = MagicMock(return_value=checkout_session_mock)

        client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(new_user.id)))

        response = client.get('/api/v1/checkout/session-status', query_string={
            'session_id': 'session_test_123',
        })

        # Assert the response
        assert response.status_code == 200

