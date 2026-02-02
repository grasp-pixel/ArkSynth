"""
LZ4AK decompression for Arknights AssetBundle files.
Based on Ark-Unpacker (BSD-3-Clause License) by Harry Huang.
https://github.com/isHarryh/Ark-Unpacker
"""
from typing import Union

import lz4.block

ByteString = Union[bytes, bytearray, memoryview]


def _read_extra_length(data: ByteString, cur_pos: int, max_pos: int) -> tuple[int, int]:
    length = 0
    while cur_pos < max_pos:
        b = data[cur_pos]
        length += b
        cur_pos += 1
        if b != 0xFF:
            break
    return length, cur_pos


def decompress_lz4ak(compressed_data: ByteString, uncompressed_size: int) -> bytes:
    """Decompresses data using LZ4AK algorithm (Arknights custom LZ4 variant)."""
    ip = 0
    op = 0
    fixed_data = bytearray(compressed_data)
    compressed_size = len(compressed_data)

    while ip < compressed_size:
        # Sequence token - swap nibbles
        literal_length = fixed_data[ip] & 0xF
        match_length = (fixed_data[ip] >> 4) & 0xF
        fixed_data[ip] = (literal_length << 4) | match_length
        ip += 1

        # Literals
        if literal_length == 0xF:
            l, ip = _read_extra_length(fixed_data, ip, compressed_size)
            literal_length += l
        ip += literal_length
        op += literal_length
        if op >= uncompressed_size:
            break

        # Match copy - swap bytes (big-endian to little-endian)
        offset = (fixed_data[ip] << 8) | fixed_data[ip + 1]
        fixed_data[ip] = offset & 0xFF
        fixed_data[ip + 1] = (offset >> 8) & 0xFF
        ip += 2
        if match_length == 0xF:
            l, ip = _read_extra_length(fixed_data, ip, compressed_size)
            match_length += l
        match_length += 4
        op += match_length

    return lz4.block.decompress(fixed_data, uncompressed_size)
