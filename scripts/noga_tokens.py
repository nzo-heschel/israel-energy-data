# Encrypted noga tokens. Need correct key to decrypt.
import base64
import os
from cryptography.fernet import Fernet


def binary_key(plain_text_key):
    padded_key = (plain_text_key + "." * 32)[:32]
    return base64.urlsafe_b64encode(padded_key.encode("utf-8"))


def encrypt_token(token, key):
    return Fernet(key).encrypt(token.encode())


def decrypt_token(encrypted_token, key):
    return Fernet(key).decrypt(encrypted_token).decode()


NOGA_KEY = binary_key(os.environ.get('NOGA_KEY'))

SMP_TOKEN = b'gAAAAABnVxB1F4Cfj95y5z6mSPWmwbmDs1p2ixBMYTqQaMs5u2Ql-4FmL8B5XwnqiCzczJAz-KpPkj36KYiuJz08hYZrUISAYg9wdpc8NfoMV5k25PwLgyk4RD2WIIt7p_bWEqGwD_2F'
PRODMIX_TOKEN = b'gAAAAABnVxB16S8AghpESP3peXHpo49y1yYzj3TolwYhsphF0basRhUwhdVQaF8TsuhpGuCC8pcrwi0iuDrJ_S2YQwqcrVI2eMYcgOA97J6ohiG52IjPIV5xLZkrfGj-cZJiSKVY-0wo'
DEMAND_TOKEN = b'gAAAAABnVxB1_XQyMriclw5FxvdU5Eu8bTNuYalbgmbO59ZkYq18t5ErnJ4ve94CxvoXLl5kzlxbqR249GQexEnpdXMaPiF_Ydk0_q49UoNWN33hHZBZQIqnMvoimB1gXnOXYGMMrDQq'
CO2_TOKEN = b'gAAAAABnVxB1YYFMExwcaO8X6T6htXBbSM55a8A85X5qjjqJuQaF3l3e1F58nOPIzku4Qd7uqT5DEhSyTCAuatrmkfmH_OjPtfOaHJbvI1WEr83ZDr1T_nxylug1yim5QL5fWFoSyyIb'
