"""
Module for handling the xxh hash for parquet files, using
only the data, ignoring the header.

This module defines the standard used in WAVES.
"""

import os
from typing import BinaryIO
import xxhash

CHUNK = 1 << 23
XXH_KEYWORD = "xxh-waves"
NO_XXH = "0"  # What a .checksums file records for files that aren't parquet.


def _calculate_data_length(file: BinaryIO, size_in_bytes: int) -> int:
    """
    Determines the end byte of the data section of a given parquet file.
    """
    end_magic_size = 8  # PAR1 and 4 byte size of footer
    start_magic_size = 4  # Leading PAR1
    file.seek(size_in_bytes - end_magic_size)
    tail = file.read(end_magic_size)
    if tail[-4:] != b"PAR1":
        raise ValueError("Not a parquet file. Missing the magic PAR1 keyword.")
    footer_len = int.from_bytes(tail[:4], "little")
    length = size_in_bytes - end_magic_size - start_magic_size - footer_len
    if length < 0:
        raise ValueError("File is corrupted; header and footer overlap.")
    return length


def calculate_hash(path: os.PathLike) -> str:
    """
    Determines the xxh128 hash for a parquet file, using only the data bytes.
    """
    size = os.path.getsize(path)
    hash = xxhash.xxh3_128()
    with open(path, "rb") as file:
        data_length = _calculate_data_length(file, size)
        file.seek(4)  # Skipping magic header
        while data_length > 0:
            block = file.read(min(CHUNK, data_length))
            if not block:
                raise IOError("Unexpected EoF.")
            hash.update(block)
            data_length -= len(block)
    return hash.hexdigest()
