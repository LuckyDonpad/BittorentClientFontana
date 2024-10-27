import copy
import hashlib
from pprint import pformat
import bencodepy
from File import File
import logging

logger = logging.getLogger(__name__)


class Torrent:
    def __init__(self, data):
        self._data = data

    @staticmethod
    def open(file):
        with open(file, 'rb') as f:
            data = bencodepy.decode(f.read())
        return Torrent(data)

    @property
    def piece_length(self):
        return self._data[b"info"][b"piece length"]

    @property
    def files(self) -> list:
        info = self._data[b'info']

        if b"length" in info:
            path = info[b"name"].decode()
            return [File(path, info[b"length"])]

        files = []
        for data in info[b'files']:
            parts = [info[b"name"]] + data[b"path"]
            path = b"/".join(parts).decode()
            files.append(File(path, data[b'length']))
        return files

    @property
    def pieces_count(self):
        return len(self._data[b"info"][b"pieces"]) // 20

    @property
    def announce_url(self) -> str:
        try:
            announce_url = self._data[b"announce"].decode()
        except Exception:
            announce_url = "nothing"
        if not (announce_url.startswith("http")): #and announce_url.endswith("announce")):
            announce_found = False
            for announce in self._data[b"announce-list"]:
                announce_url = announce[0].decode()
                if announce_url.startswith("http") and announce_url.endswith("announce"):
                    announce_found = True
                    break
            if not announce_found:
                raise RuntimeError("No http-like announce in torrent")
        return announce_url

    @property
    def size(self) -> int:
        return sum(f.length for f in self.files)

    @property
    def info_hash(self) -> bytes:
        return hashlib.sha1(bencodepy.encode(self._data[b"info"])).digest()

    def get_piece_hash(self, index):
        return self._data[b"info"][b"pieces"][index * 20:index * 20 + 20]

    def __str__(self) -> str:
        data = copy.deepcopy(self._data)
        data[b'info'][b'pieces'] = b'OMITTED'
        return pformat(data)
