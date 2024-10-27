import logging
import sys
import asyncio

from FileManager import FileManager
from Torrent import Torrent
from utils import make_peer_id
from Tracker import Tracker
from Peer import Peer

logger = logging.getLogger(__name__)


async def main():
    torrent = Torrent.open("kali-linux-2024.3-installer-amd64.iso.torrent")
    print(torrent)
    file_manager = FileManager(torrent)

    peer_id = make_peer_id()
    logger.info(f"Peer id: {peer_id}")

    tracker = Tracker(torrent, peer_id)
    peers_info = await tracker.get_peers()
    peers = [Peer(torrent, file_manager, peer_id, ip, port) for ip, port in peers_info]
    logger.info(f"Got {len(peers_info)} peers")
    for ip, port in peers_info:
        logger.info(f"{ip}:{port}")

    tasks = [p.download() for p in peers]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="[%(asctime)s] {%(name)s:%(lineno)d} %(levelname)s - %(message)s",
                        datefmt="%H:%M:%S")
    asyncio.run(main())
