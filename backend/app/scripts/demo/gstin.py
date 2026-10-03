"""GSTIN generation. Format: 2-digit state code + 10-char PAN + entity number + 'Z' + checksum.
The checksum is the official mod-36 check character, so generated numbers pass validation."""

import random

CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_DIGITS = "0123456789"


def checksum(first_fourteen: str) -> str:
    total = 0
    for index, char in enumerate(first_fourteen):
        factor = 1 if index % 2 == 0 else 2
        product = factor * CHARSET.index(char)
        total += product // 36 + product % 36
    return CHARSET[(36 - total % 36) % 36]


def gstin(rng: random.Random, state_code: str) -> str:
    pan = (
        "".join(rng.choice(_LETTERS) for _ in range(5))
        + "".join(rng.choice(_DIGITS) for _ in range(4))
        + rng.choice(_LETTERS)
    )
    # Fourth PAN character is the holder type; C = company, F = firm/LLP.
    pan = pan[:3] + rng.choice("CF") + pan[4:]
    body = f"{state_code}{pan}{rng.choice('123456789')}Z"
    return body + checksum(body)
