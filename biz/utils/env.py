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
        self.JWT_SECRET = os.getenv("JWT_SECRET")
        self.JWT_HEADER = os.getenv("JWT_HEADER")
        self.LOG_LEVEL = os.getenv("LOG_LEVEL")
