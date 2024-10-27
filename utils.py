import string
import random

BLOCK_LENGTH = 2 ** 14


def make_peer_id() -> str:
    return "-MW-" + "".join([random.choice(string.ascii_lowercase + string.digits) for _ in range(16)])
