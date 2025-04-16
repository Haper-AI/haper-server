import os
import dotenv

dotenv.load_dotenv()


class RuntimeEnv:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(RuntimeEnv, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    @staticmethod
    def Instance():
        if not RuntimeEnv._instance:
            RuntimeEnv()
        return RuntimeEnv._instance

    def __init__(self):
        self.APP_NAME = os.getenv("APP_NAME")

        # jwt auth
        self.JWT_AUTH_SECRET = os.getenv("JWT_AUTH_SECRET")
        self.JWT_AUTH_COOKIE_NAME = os.getenv("JWT_AUTH_COOKIE_NAME")

        # logger
        self.LOG_LEVEL = os.getenv("LOG_LEVEL")

        # db
        self.POSTGRES_DSN = os.getenv("POSTGRES_DSN")

        # cors
        self.ALLOW_ORIGINS = os.getenv("ALLOW_ORIGINS", "").split(",")

        # google
        self.GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
        self.GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

        # aws
        self.AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
        self.AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
        ## aws sqs
        self.SQS_REGION = os.getenv("SQS_REGION")
        self.SQS_ENDPOINT = os.getenv("SQS_ENDPOINT")
        self.SQS_REPORT_ASYNC_ACTION_QUEUE_URL = os.getenv("SQS_REPORT_ASYNC_ACTION_QUEUE_URL")

        ## aws secret manager
        self.AWS_SM_REGION = os.getenv("AWS_SM_REGION")
        self.AWS_SM_SECRET_NAME = os.getenv("AWS_SM_SECRET_NAME")
        self.AWS_SM_KEY_NAME_OUTLOOK_SUB_PRIVATE = os.getenv("AWS_SM_KEY_NAME_OUTLOOK_SUB_PRIVATE")
        self.AWS_SM_KEY_NAME_OUTLOOK_SUB_PUBLIC = os.getenv("AWS_SM_KEY_NAME_OUTLOOK_SUB_PUBLIC")

        # google cloud
        self.GMAIL_WATCH_PUB_SUB_TOPIC = os.getenv("GMAIL_WATCH_PUB_SUB_TOPIC")

        # microsoft azure
        self.MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID")
        self.MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET")
        self.OUTLOOK_SYNC_WEBHOOK_URL = os.getenv("OUTLOOK_SYNC_WEBHOOK_URL")
        self.MICROSOFT_CERTIFICATE_KEY_ID = os.getenv("MICROSOFT_CERTIFICATE_KEY_ID")

