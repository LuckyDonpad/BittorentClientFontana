import bencodepy
from Torrent import Torrent
from urllib.parse import quote
import tornado
import logging
from pprint import pformat

logger = logging.getLogger(__name__)


class Tracker:
    def __init__(self, torrent: Torrent, peer_id: str):
        self._torrent = torrent
        self._peer_id = peer_id

    async def get_peers(self):
        data = await self._request_peers_data()
        peers = self._parse_peers(data[b"peers"])
        return peers

    async def _request_peers_data(self):
        http_client = tornado.httpclient.AsyncHTTPClient()
        url = self._torrent.announce_url + "?" + "&".join(f"{k}={v}" for k, v in self._get_params().items())
        logger.info(f"Tracker request: {url}")
        try:
            resp = await http_client.fetch(url)
        except Exception as e:
            logger.error(f"Tracker response: {str(e)}")
            raise RuntimeError("Tracker failed to get peers data")
        data = bencodepy.decode(resp.body)
        logger.info(f"Tracker response {pformat(data)}")
        return data

    def _get_params(self):
        return {
            "info_hash": quote(self._torrent.info_hash),
            "peer_id": self._peer_id,
            "port": 8861,
            "uploaded": 0,
            "downloaded": 0,
            "left": self._torrent.size,
            "event": "started",
            "compact": 1,
            "numwant": 50
        }

    def _parse_peers(self, data):
        assert isinstance(data, bytes)
        peers = []
        for i in range(0, len(data), 6):
            ip_addr = ".".join(f"{c}" for c in data[i:i + 4])
            port = data[i + 4] * 256 + data[i + 5]
            peers.append((ip_addr, port))
        return peers
