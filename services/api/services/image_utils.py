"""Image helpers.

Deliberately dependency-free (no Pillow): MIME detection and dimension parsing
are done from the file's magic bytes and header fields, which is all the
visual-inspection feature needs.
"""

from __future__ import annotations

_DATA_URI_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
}

_JPEG_SOF_MARKERS = {
    0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
    0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
}


def detect_mime_type(data: bytes) -> str | None:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def extension_for(mime_type: str) -> str:
    return _DATA_URI_MIME.get(mime_type, ".bin")


def image_dimensions(data: bytes) -> tuple[int | None, int | None]:
    """Return (width, height) if they can be parsed, else (None, None)."""
    try:
        mime = detect_mime_type(data)
        if mime == "image/png":
            return (
                int.from_bytes(data[16:20], "big"),
                int.from_bytes(data[20:24], "big"),
            )
        if mime == "image/gif":
            return (
                int.from_bytes(data[6:8], "little"),
                int.from_bytes(data[8:10], "little"),
            )
        if mime == "image/jpeg":
            return _jpeg_dimensions(data)
        if mime == "image/webp":
            return _webp_dimensions(data)
    except (IndexError, ValueError):
        return (None, None)
    return (None, None)


def _jpeg_dimensions(data: bytes) -> tuple[int | None, int | None]:
    index = 2
    length = len(data)
    while index + 9 < length:
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        if marker in _JPEG_SOF_MARKERS:
            height = int.from_bytes(data[index + 5:index + 7], "big")
            width = int.from_bytes(data[index + 7:index + 9], "big")
            return (width, height)
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            index += 2
            continue
        segment_length = int.from_bytes(data[index + 2:index + 4], "big")
        if segment_length <= 0:
            break
        index += 2 + segment_length
    return (None, None)


def _webp_dimensions(data: bytes) -> tuple[int | None, int | None]:
    chunk = data[12:16]
    if chunk == b"VP8X":
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        return (width, height)
    if chunk == b"VP8 ":
        width = int.from_bytes(data[26:28], "little") & 0x3FFF
        height = int.from_bytes(data[28:30], "little") & 0x3FFF
        return (width, height)
    if chunk == b"VP8L":
        bits = int.from_bytes(data[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return (width, height)
    return (None, None)


__all__ = [
    "detect_mime_type",
    "extension_for",
    "image_dimensions",
]
