import os

import bitstring


class FileManager:
    def __init__(self, torrent):
        self._files = torrent.files
        self._create_empty_files()
        self._used_pieces = bitstring.BitArray(length=torrent.pieces_count)
        self._piece_len = torrent.piece_length

    def _create_empty_files(self):
        for f in self._files:
            dir_path = f.path[:f.path.rfind("/")]
            os.makedirs(dir_path, exist_ok=True)
            with open(f.path, "wb") as fd:
                fd.seek(f.length - 1)
                fd.write(b'\0')

    @property
    def used_pieces(self):
        return self._used_pieces

    def save_piece(self, piece, piece_id):
        piece_left = piece_id * self._piece_len
        piece_right = piece_left + len(piece)

        file_delta = 0
        for f in self._files:
            file_left = file_delta
            file_right = file_left + f.length
            file_delta = file_right

            part_left = max(file_left, piece_left)
            part_right = min(file_right, piece_right)

            if part_left < part_right:
                with open(f.path, "r+b") as fd:
                    fd.seek(part_left - file_left)
                    piece_part = piece[part_left - piece_left : part_right - piece_left]
                    fd.write(piece_part)
