import stripe

from biz.utils.env import RuntimeEnv

stripe.api_key = RuntimeEnv.Instance().STRIPE_API_KEY
