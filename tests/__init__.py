import random
import string

def generate_random_string(length):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def generate_random_gmail(length):
    return f"{generate_random_string(length)}@gmail.com"

def generate_random_outlook_email(length):
    return f"{generate_random_string(length)}@outlook.com"