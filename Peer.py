import hashlib
import random
from enum import IntEnum
import logging
import asyncio

from FileManager import FileManager
from Torrent import Torrent
import bitstring
from utils import BLOCK_LENGTH

logger = logging.getLogger(__name__)


class MessageType(IntEnum):
    CHOKE = 0
    UNCHOKE = 1
    INTERESTED = 2
    NOT_INTERESTED = 3
    HAVE = 4
    BITFIELD = 5
    REQUEST = 6
    PIECE = 7
    CANCEL = 8


class Peer:
    def __init__(self, torrent: Torrent, file_manager: FileManager, peer_id: str, host: str, port: int):
        self._host = host
        self._port = port
        self._torrent = torrent
        self._peer_id = peer_id
        self._file_manager = file_manager

        self._have_pieces = None
        self._cur_piece_id = None
        self._cur_blocks = None

        self._writer = None
        self._reader = None

        self._choked = True

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    async def _write(self, data):
        self._writer.write(data)
        await self._writer.drain()

    async def _read(self, n):
        try:
            return await self._reader.readexactly(n)
        except:
            return b""

    def _handshake(self):
        msg = b""
        msg += chr(19).encode()
        msg += b"BitTorrent protocol"
        msg += b"\0" * 8
        msg += self._torrent.info_hash
        msg += self._peer_id.encode()
        return msg

    async def download(self):
        try:
            self._reader, self._writer = await asyncio.wait_for(asyncio.open_connection(self._host, self._port),
                                                                timeout=2)
        except Exception as e:
            self.log_error(f"Failed to connect, reason \"{str(e)}\"")
            return

        self.log_info("Send handshake")
        handshake = self._handshake()
        await self._write(handshake)

        resp = await self._read(len(handshake))
        if not resp:
            self.log_error("Failed to get handshake, disconnecting")
            return
        self.log_info(f"Got handshake, peer id {resp[48:]}")

        while True:
            len_bytes = await self._read(4)
            if not len_bytes:
                self.log_info("No messages, disconnecting")
                break

            len_value = int.from_bytes(len_bytes, byteorder="big")
            self.log_info(f"Got message of length{len_value}")

            if len_value == 0:
                self.log_info("[Message] Keep Alive")
                continue

            msg = await self._read(len_value)
            if not msg:
                self.log_error("[Message] Can't read message, disconnecting")

            msg_id = int(msg[0])

            if msg_id == MessageType.CHOKE:
                self.log_info("[Message] Choke")
                self._choked = True

            elif msg_id == MessageType.UNCHOKE:
                self.log_info("[Message] Unchoke")
                self._choked = False

            elif msg_id == MessageType.INTERESTED:
                self.log_info("[Message] Interested")

            elif msg_id == MessageType.NOT_INTERESTED:
                self.log_info("[Message] Not interested")

            elif msg_id == MessageType.HAVE:
                self.log_info("[Message] Have")

            elif msg_id == MessageType.BITFIELD:
                self._have_pieces = bitstring.BitArray(bytes=msg[1:], length=self._torrent.pieces_count)
                self.log_info(f"[Message] Bitfield: {self._have_pieces}")

                self.log_info("Sending Interested message")
                interested_msg = b"\0\0\0\1" + b"\2"
                await self._write(interested_msg)

            elif msg_id == MessageType.REQUEST:
                self.log_info("[Message] Request")

            elif msg_id == MessageType.PIECE:
                piece_id = int.from_bytes(msg[1:5], byteorder="big")
                begin = int.from_bytes(msg[5:9], byteorder="big")
                data = msg[9:]
                self.log_info(f"[Message] Piece [index {piece_id}, begin {begin}, length {len(data)}]")

                assert begin in self._cur_blocks
                self._cur_blocks[begin] = data
                if None not in self._cur_blocks.values():
                    self._on_all_blocks_downloaded()

            elif msg_id == MessageType.CANCEL:
                self.log_info("[Message] Cancel")

            else:
                self.log_info(f"[Message] Unknown message id: {msg_id}")

            if self._cur_piece_id is None and not self._choked:
                res = await self._request_new_piece()
                if not res:
                    self.log_info("Nothing to download, disconnect")
        self._writer.close()
        await self._writer.wait_closed()
        self.log_info(f"Connection closed")

    def _choose_piece_id(self):
        used_pieces = self._file_manager.used_pieces

        needed_pieces = used_pieces.copy()
        needed_pieces.invert()

        available_pieces = needed_pieces & self._have_pieces
        piece_ids = [i for i in range(len(available_pieces)) if available_pieces[i]]

        if not piece_ids:
            return None
        piece_id = random.choice(piece_ids)
        used_pieces[piece_id] = True
        return piece_id

    async def _request_new_piece(self):
        piece_id = self._choose_piece_id()
        if piece_id is None:
            return False

        self.log_info(f"Will download piece: {piece_id}")

        piece_len = self._torrent.piece_length
        size = self._torrent.size

        piece_begin = piece_id * piece_len
        l = piece_begin
        r = min(l + BLOCK_LENGTH, size)

        blocks = {}
        msgs = []
        for i in range(piece_len // BLOCK_LENGTH):
            index = piece_id
            begin = l - piece_begin
            length = r - l

            blocks[begin] = None

            msg = b""
            msg += int.to_bytes(13, length=4, byteorder="big")
            msg += chr(MessageType.REQUEST).encode()
            msg += int.to_bytes(index, length=4, byteorder="big")
            msg += int.to_bytes(begin, length=4, byteorder="big")
            msg += int.to_bytes(length, length=4, byteorder="big")
            msgs.append(msg)

            self.log_info(f"Request block [undex {index}, begin {begin}, length {length}]")

            l += BLOCK_LENGTH
            r = min(l + BLOCK_LENGTH, size)
            if l >= size:
                break

        self._cur_piece_id = piece_id
        self._cur_blocks = blocks

        for msg in msgs:
            await self._write(msg)

        return True

    def _join_blocks(self):
        res = b""
        for k in sorted(set(self._cur_blocks)):
            res += self._cur_blocks[k]
        return res

    def _on_all_blocks_downloaded(self):
        piece = self._join_blocks()
        expected_piece_hash = self._torrent.get_piece_hash(self._cur_piece_id)
        actual_piece_hash = hashlib.sha1(piece).digest()
        assert expected_piece_hash == actual_piece_hash

        self._file_manager.save_piece(piece, self._cur_piece_id)

        self._cur_piece_id = None
        self._cur_blocks = None

    def log_info(self, log):
        logger.info(f"{self} {log}")

    def log_error(self, log):
        logger.error(f"{self} {log}")

    def __repr__(self) -> str:
        return f"[Peer {self._host}:{self._port}]"
