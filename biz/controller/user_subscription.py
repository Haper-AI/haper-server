from datetime import datetime, timezone
from typing import Literal

from biz.dal.user import User
from biz.dal.user_subscription import UserSubscription
from biz.service.stripe import stripe
from biz.service.db import get_session
from biz.utils.env import RuntimeEnv
from biz.utils.logger import logger
from biz.utils.response import ResponseCode

price_map = {
    "month": "price_1RH6amRfaFuQLicPoypAVEvt",
    # "year": "price_1REZjoRfaFuQLicP6EO2X6ui"
}


def new_checkout_session(user_id, user_email, stripe_customer_id, return_url, billing_cycle: Literal["month"]):
    """
    Create a new checkout session with Stripe.
    This function is called when a user initiates a payment.
    """
    # customer_id = None
    with get_session(write=False) as session:
        user_subscription = UserSubscription.get_by_user_id(session, user_id)
        if user_subscription:
            # customer_id = user_subscription.stripe_customer_id
            raise ResponseCode.UnsupportedAction.create_error("user subscription already exists")

    session = stripe.checkout.Session.create(
        ui_mode='embedded',
        line_items=[
            {
                'price': price_map[billing_cycle],
                'quantity': 1
            }
        ],
        mode='subscription',
        payment_method_types=["card"],
        customer=stripe_customer_id,
        customer_email=user_email if not stripe_customer_id else None,
        subscription_data={
            "trial_period_days": RuntimeEnv.Instance().STRIPE_SUBSCRIPTION_TRIAL_DAYS
        } if not stripe_customer_id else None,
        return_url=f"{return_url}?session_id={{CHECKOUT_SESSION_ID}}",
    )

    return session.id, session.client_secret


def handle_customer_subscription_created(subscription):
    """
    Handle the customer.subscription.created event from Stripe.
    This function is called when a new subscription is created.
    """
    stripe_customer_id = subscription["customer"]
    stripe_subscription_id = subscription["id"]
    subscription_cycle = subscription["items"]["data"][0]["plan"]["interval"]
    subscription_status = subscription["status"]
    trial_end_timestamp = subscription["trial_end"]

    trial_end_at = None
    if trial_end_timestamp:
        trial_end_at = datetime.fromtimestamp(trial_end_timestamp, timezone.utc)

    # Get customer email using stripe API
    stripe_customer = stripe.Customer.retrieve(stripe_customer_id)
    user_email = stripe_customer["email"]

    if not user_email:
        logger.warning("user email not found")
        return

    # Add the new subscription to the database
    with get_session(write=True) as session:
        # Get user ID from the database using the email
        user = User.get_by_email(session, user_email)
        if not user:
            logger.warning("user with email {} not found".format(user_email))
            return

        # set user stripe customer id if not exists
        if not user.stripe_customer_id:
            User.update(session, user.id, stripe_customer_id)

        UserSubscription.add(
            session,
            user_id=user.id,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            subscription_cycle=subscription_cycle,
            subscription_status=subscription_status,
            trial_end_at=trial_end_at
        )


def handle_customer_subscription_update(subscription):
    """
    Handle the customer.subscription.updated event from Stripe.
    This function is called when an existing subscription is updated.
    """
    stripe_customer_id = subscription["customer"]
    subscription_cycle = subscription["items"]["data"][0]["plan"]["interval"]
    subscription_status = subscription["status"]

    # Update the existing subscription in the database
    with get_session(write=True) as session:
        user_subscription = UserSubscription.get_by_stripe_customer_id(session, stripe_customer_id)
        UserSubscription.update(
            session,
            user_subscription.user_id,
            subscription_status,
            subscription_cycle
        )


# def handle_customer_subscription_trail_will_end(subscription):
#     """
#     Handle the customer.subscription.trial_will_end event from Stripe.
#     This function is called when a trial period is about to end.
#     """
#     stripe_subscription_id = subscription["id"]
#     trial_end = subscription["trial_end"]
#
#     # Update the existing subscription in the database
#     trial_end = subscription["trial_end"]
#
#     trial_end_time = datetime.fromtimestamp(trial_end)
#
#     if datetime.now() >= trial_end_time:
#
#
#     return


def handle_customer_subscription_paused(subscription):
    """
    Handle the customer.subscription.paused event from Stripe.
    This function is called when a subscription is paused.
    """
    stripe_customer_id = subscription["customer"]
    subscription_status = subscription["status"]

    # Update the existing subscription in the database
    with get_session(write=True) as session:
        user_subscription = UserSubscription.get_by_stripe_customer_id(session, stripe_customer_id)
        UserSubscription.update(session, user_subscription.user_id, subscription_status)


def handle_customer_subscription_resumed(subscription):
    """
    Handle the customer.subscription.resumed event from Stripe.
    This function is called when a subscription is resumed.
    """
    stripe_customer_id = subscription["customer"]
    subscription_status = subscription["status"]

    # Update the existing subscription in the database
    with get_session(write=True) as session:
        user_subscription = UserSubscription.get_by_stripe_customer_id(session, stripe_customer_id)
        UserSubscription.update(session, user_subscription.user_id, subscription_status)


def handle_customer_subscription_deleted(subscription):
    """
    Handle the customer.subscription.deleted event from Stripe.
    This function is called when a subscription is deleted.
    """
    stripe_customer_id = subscription["customer"]

    # Update the existing subscription in the database

    with get_session(write=True) as session:
        UserSubscription.delete_by_stripe_customer_id(session, stripe_customer_id)

# def handle_invoice_paid(invoice):
#     """
#     Handle the invoice.paid event from Stripe.
#     This function is called when an invoice is paid.
#     """
#     stripe_invoice_id = invoice["id"]
#     subscription_status = invoice["status"]
#
#     # Update the existing subscription in the database
#
#     return
#
#
# def handle_invoice_payment_failed(invoice):
#     """
#     Handle the invoice.payment_failed event from Stripe.
#     This function is called when an invoice payment fails.
#     """
#     stripe_invoice_id = invoice["id"]
#     subscription_status = invoice["status"]
#
#     # Update the existing subscription in the database
#
#     return
