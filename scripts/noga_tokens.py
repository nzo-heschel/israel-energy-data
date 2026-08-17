# Encrypted noga tokens. Need correct key to decrypt.
import base64
import os
from cryptography.fernet import Fernet


def binary_key(plain_text_key):
    if not plain_text_key:
        plain_text_key = "default_key"
    padded_key = (plain_text_key + "." * 32)[:32]
    return base64.urlsafe_b64encode(padded_key.encode("utf-8"))


def encrypt_token(token, key):
    return Fernet(key).encrypt(token.encode())


def decrypt_token(encrypted_token, key):
    return Fernet(key).decrypt(encrypted_token).decode()


NOGA_KEY = binary_key(os.environ.get('NOGA_KEY'))

SMP_TOKEN = b'gAAAAABqg2YAScD4Grrzw9oeY1BH7ne8BZePn5NPCO-1o2hKLr7TSPclkn4sECBLzNL-MvzHKWpcVhydHd-RvcswDASN00ZaqHwet-8XboVO7Xal5NrakQq8yLPTZycIUj6zVKe09M4K'
PRODMIX_TOKEN = b'gAAAAABqg2YA08HY4TwONSTRzO0RasLgAPDrNBKhVoKLSJ1e2aMftOnkldGr0TcVygCMpe4dRe5y_rHsnkRfRFnI_8Td3yvzZ4bOltmkGvKLqQ7XMKMxIfzcOdBAkjg6327Bcqhjh2Fh'
DEMAND_TOKEN = b'gAAAAABqg2YAA7gOsNwA5Flyqfuq8n9_ETXDS1kWxufXnDdYWtyOI5Q3cErwDudPo16nt4W3t_Sp7c0p2Xbx0ht0DSOrbXqQ75ccJag_zLf74Ae0VrUOIHiDHdnYaTmnLlHRG_9-5iwW'
CO2_TOKEN = b'gAAAAABqg2YAdXVtvKx2gz1aB0Mr5jYV3vPy-RURtxK5dBGpVcbSocSMnj1hIgqiAnK0MtY6ym-by-V-7uJEX4iTA2ECMIASQZEIeqjWmPF4ei1V4FG7urIPEd8ASrabZ2-93kWBgiZS'
