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

SMP_TOKEN = b'gAAAAABqY3pXpZ3ebBXm9bqOojIm7gmnSv2HX-qI4tvwhfoJWHinknxH6_3q6-H_HNMLOAUs7QUvkITCYGxSkTUND27vsFR6F-5uOV3idT4aCzuzxAk7x_gpp5DiZDnAHKntWMfNeKBg'
PRODMIX_TOKEN = b'gAAAAABqY3pXAPY-T44p2GPw_tGuQ9DP_DBbw6NGE27yt2sSMJkE0Zr_3lWBfc-Ui48uWMuk6gPYicoGGpBsSJAEHN2zl_zYjpgy6wQkPeU7VFPmLqb_KP2lvpVTrlcNn3h0DB5Bfe11'
DEMAND_TOKEN = b'gAAAAABqY3pXnpP0TPpNnnP-vZYZmwVPaAYgd28vzll5PYqs83B2wfV2u5DsEl47Sfck-0Y4fZKV7QzcdzhgwI0i5W5UTEO49SfjTIBCdvsLOzgQl5iv0bQx7S19-Dc96RziwPm8L0tL'
CO2_TOKEN = b'gAAAAABqY3pXP9tfgscN7swJlC4IfCoVBlOpdJQX1fgKJZS2xaCKEJekskzGlyMyewmCq09cSwpYE6dpNHBObN9nSShOoKO5Ng_zqcaXCYbre9vdkt06lGz2JFvbW0nZxDeLevCd4lTc'
