"""
Module for inserting metadata into parquet footers without reading the full file.
"""

from __future__ import annotations

import os
from enum import IntEnum
from pathlib import Path


__all__ = ["write_keyword_metadata", "ParquetFooterError", "MAGIC", "TAIL_SIZE"]

MAGIC = b"PAR1"
TAIL_SIZE = 8  # 4-byte footer length + the trailing PAR1 magic.
KEY_VALUE_FIELD_ID = 5  # FileMetaData.key_value_metadata
_U64_MASK = 0xFFFF_FFFF_FFFF_FFFF


class ParquetFooterError(Exception):
    """Raised when the file is not a plain Parquet file or the footer is malformed."""


class ThriftID(IntEnum):
    STOP = 0
    BOOL_TRUE = 1
    BOOL_FALSE = 2
    I8 = 3
    I16 = 4
    I32 = 5
    I64 = 6
    DOUBLE = 7
    BINARY = 8
    LIST = 9
    SET = 10
    MAP = 11
    STRUCT = 12

    @classmethod
    def from_byte(cls, value: int) -> "ThriftID":
        try:
            return cls(value)
        except ValueError:
            raise ParquetFooterError(f"unsupported thrift type id {value}") from None


def write_keyword_metadata(path: os.PathLike, keyword: str, value: str) -> None:
    """Insert or replace ``keyword`` in ``path``'s footer metadata, in place."""
    path = Path(path)
    file_len = os.path.getsize(path)
    with open(path, "r+b") as file:
        smallest_possible = TAIL_SIZE + len(MAGIC)
        if file_len < smallest_possible:
            raise ParquetFooterError(
                f"{path}: not a parquet file (smaller than {smallest_possible} bytes)"
            )

        # Last TAIL_SIZE bytes: [metadata_len u32 LE][PAR1].
        file.seek(-TAIL_SIZE, os.SEEK_END)
        tail = file.read(TAIL_SIZE)
        if tail[-len(MAGIC) :] != MAGIC:
            raise ParquetFooterError(
                f"{path}: missing PAR1 footer magic (encrypted or non-parquet?)"
            )
        metadata_len = int.from_bytes(tail[:4], "little")
        footer_start = file_len - TAIL_SIZE - metadata_len
        if footer_start < 0:
            raise ParquetFooterError("declared footer length exceeds file size")

        file.seek(footer_start)
        blob = file.read(metadata_len)
        if len(blob) != metadata_len:
            raise ParquetFooterError("could not read the declared footer length")

        new_blob = _upsert_kv(blob, keyword, value)
        if len(new_blob) > 0xFFFF_FFFF:
            raise ParquetFooterError("new footer exceeds the u32 length field")

        # Overwrite only the tail, starting exactly where the old footer began.
        file.seek(footer_start)
        file.write(new_blob)
        file.write(len(new_blob).to_bytes(4, "little"))
        file.write(MAGIC)

        # The new footer may be shorter or longer than the old one; set exact length.
        file.truncate(footer_start + len(new_blob) + TAIL_SIZE)
        file.flush()
        os.fsync(file.fileno())


class _Cursor:
    """A byte buffer plus a read position, standing in for Rust's ``&mut usize``."""

    __slots__ = ("buf", "pos")

    def __init__(self, buf: bytes, pos: int = 0) -> None:
        self.buf = buf
        self.pos = pos

    def byte(self) -> int:
        if self.pos >= len(self.buf):
            raise ParquetFooterError("overran footer while parsing")
        b = self.buf[self.pos]
        self.pos += 1
        return b

    def advance(self, n: int) -> None:
        self.pos += n
        if self.pos > len(self.buf):
            raise ParquetFooterError("overran footer while parsing")


def _upsert_kv(blob: bytes, key: str, value: str) -> bytes:
    """Walk the top-level ``FileMetaData`` fields and upsert ``key``=``value``."""
    cur = _Cursor(blob)
    last_id = 0

    while True:
        field_start = cur.pos
        type_id, field_id, last_id = _read_field_header(cur, last_id)

        if type_id is ThriftID.STOP:
            # No field 5 anywhere: insert a fresh one right before STOP.
            field = _encode_kv_field([(key, value)])
            return blob[:field_start] + field + blob[field_start:]

        if field_id == KEY_VALUE_FIELD_ID:
            if type_id is not ThriftID.LIST:
                raise ParquetFooterError(
                    f"key_value_metadata is not a list (thrift type {type_id.name})"
                )
            elem_type, count = _read_collection_header(cur)
            if count > 0 and elem_type is not ThriftID.STRUCT:
                raise ParquetFooterError("key_value_metadata elements are not structs")
            pairs = [_parse_key_value(cur) for _ in range(count)]
            list_end = cur.pos  # first byte after the list = next field header

            pairs = [(k, v) for (k, v) in pairs if k != key]
            pairs.append((key, value))

            field = _encode_kv_field(pairs)
            return blob[:field_start] + field + blob[list_end:]

        _skip_value(cur, type_id)


def _encode_kv_field(pairs: list[tuple[str, str | None]]) -> bytes:
    """Encode a complete ``FileMetaData`` field 5 from ``pairs``.

    Uses the long-form field header (absolute id 5) so that neighbouring
    fields' delta encoding stays valid regardless of where this lands.
    """
    out = bytearray()
    out.append(ThriftID.LIST)  # delta 0 (long form) + type LIST
    _write_uvarint(out, _zigzag(KEY_VALUE_FIELD_ID))
    _write_collection_header(out, ThriftID.STRUCT, len(pairs))
    for k, v in pairs:
        kb = k.encode("utf-8")
        out.append((1 << 4) | ThriftID.BINARY)  # field 1: key
        _write_uvarint(out, len(kb))
        out += kb
        if v is not None:
            vb = v.encode("utf-8")
            out.append((1 << 4) | ThriftID.BINARY)  # field 2: value
            _write_uvarint(out, len(vb))
            out += vb
        out.append(ThriftID.STOP)
    return bytes(out)


def _parse_key_value(cur: _Cursor) -> tuple[str, str | None]:
    """Decode one ``KeyValue`` struct, ignoring any unknown fields."""
    last_id = 0
    key: str | None = None
    value: str | None = None
    while True:
        type_id, field_id, last_id = _read_field_header(cur, last_id)
        if type_id is ThriftID.STOP:
            break
        if type_id is ThriftID.BINARY:
            s = _read_binary_str(cur)
            if field_id == 1:
                key = s
            elif field_id == 2:
                value = s
            # other field ids: unknown, ignored
        else:
            _skip_value(cur, type_id)
    if key is None:
        raise ParquetFooterError("KeyValue missing required key")
    return key, value


def _read_field_header(cur: _Cursor, last_id: int) -> tuple[ThriftID, int, int]:
    """Read a field header; returns ``(type_id, field_id, new_last_id)``.

    Short form  ``ddddtttt``          -- id delta in the high nibble.
    Long form   ``0000tttt`` + varint -- absolute zigzag id follows.
    Stop field  ``00000000``.
    """
    buffer = cur.byte()
    if buffer == 0:
        return ThriftID.STOP, 0, last_id
    type_id = ThriftID.from_byte(buffer & 0x0F)
    delta = buffer >> 4
    field_id = _unzigzag(_read_uvarint(cur)) if delta == 0 else last_id + delta
    return type_id, field_id, field_id


def _read_collection_header(cur: _Cursor) -> tuple[ThriftID, int]:
    """Read a list/set header; returns ``(element_type, count)``.

    Short form ``sssstttt``; if ``ssss == 0b1111`` the count is an unsigned
    varint (not zigzag) that follows.
    """
    header = cur.byte()
    elem_type = ThriftID.from_byte(header & 0x0F)
    count = header >> 4
    if count == 15:
        count = _read_uvarint(cur)
    return elem_type, count


def _write_collection_header(
    out: bytearray, element_type: ThriftID, count: int
) -> None:
    if count < 15:
        out.append((count << 4) | element_type)
    else:
        out.append(0xF0 | element_type)
        _write_uvarint(out, count)


def _skip_value(cur: _Cursor, type_id: ThriftID) -> None:
    """Advance the cursor past one value of ``type_id`` (field context)."""
    if type_id in (ThriftID.BOOL_TRUE, ThriftID.BOOL_FALSE):
        pass  # the value lives in the type nibble
    elif type_id is ThriftID.I8:
        cur.advance(1)
    elif type_id in (ThriftID.I16, ThriftID.I32, ThriftID.I64):
        _read_uvarint(cur)  # zigzag then varint; we only need the length
    elif type_id is ThriftID.DOUBLE:
        cur.advance(8)
    elif type_id is ThriftID.BINARY:
        cur.advance(_read_uvarint(cur))
    elif type_id in (ThriftID.LIST, ThriftID.SET):
        elem_type, count = _read_collection_header(cur)
        if elem_type in (ThriftID.BOOL_TRUE, ThriftID.BOOL_FALSE):
            cur.advance(count)  # bools cost one byte each inside a collection
        else:
            for _ in range(count):
                _skip_value(cur, elem_type)
    elif type_id is ThriftID.MAP:
        n_pairs = _read_uvarint(cur)  # number of pairs, not bytes
        if n_pairs > 0:
            kv = cur.byte()  # kkkkvvvv
            kt = ThriftID.from_byte(kv >> 4)
            vt = ThriftID.from_byte(kv & 0x0F)
            for _ in range(n_pairs):
                _skip_element(cur, kt)
                _skip_element(cur, vt)
    elif type_id is ThriftID.STRUCT:
        last_id = 0
        while True:
            inner_type, _, last_id = _read_field_header(cur, last_id)
            if inner_type is ThriftID.STOP:
                break
            _skip_value(cur, inner_type)
    else:  # ThriftID.STOP
        raise ParquetFooterError(
            "malformed header: STOP found where it shouldn't be and was not handled"
        )
    if cur.pos > len(cur.buf):
        raise ParquetFooterError("overran footer while parsing")


def _skip_element(cur: _Cursor, type_id: ThriftID) -> None:
    """Like ``_skip_value`` but for map keys/values, where bools take a byte."""
    if type_id in (ThriftID.BOOL_TRUE, ThriftID.BOOL_FALSE):
        cur.advance(1)
    else:
        _skip_value(cur, type_id)


def _read_binary_str(cur: _Cursor) -> str:
    length = _read_uvarint(cur)
    start = cur.pos
    cur.advance(length)
    return cur.buf[start : cur.pos].decode("utf-8")


def _read_uvarint(cur: _Cursor) -> int:
    result = 0
    shift = 0
    while True:
        byte = cur.byte()
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result
        shift += 7
        if shift >= 64:
            raise ParquetFooterError("varint too long")


def _write_uvarint(out: bytearray, v: int) -> None:
    while True:
        byte = v & 0x7F
        v >>= 7
        if v:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return


def _zigzag(v: int) -> int:
    """Signed -> unsigned, so small negatives stay short as varints."""
    return ((v << 1) ^ (v >> 63)) & _U64_MASK


def _unzigzag(v: int) -> int:
    """Unsigned -> signed; inverse of :func:`_zigzag`."""
    return (v >> 1) ^ -(v & 1)
