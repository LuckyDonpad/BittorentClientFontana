class File:
    def __init__(self, path: str, length: int):
        self._path = path
        self._length = length

    @property
    def path(self) -> str:
        return self._path

    @property
    def length(self) -> int:
        return self._length
