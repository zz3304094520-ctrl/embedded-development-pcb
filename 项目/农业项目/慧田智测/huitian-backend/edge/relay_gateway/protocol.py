"""DiuStone two-channel USB relay protocol."""

from __future__ import annotations

import re


START_BYTE = 0xA0
ALL_CHANNELS = 0x0F
OP_OFF = 0x00
OP_ON = 0x01
OP_QUERY = 0x02


class RelayProtocolError(ValueError):
    """Raised when a relay frame or response is invalid."""


def build_frame(channel: int, operation: int) -> bytes:
    """Build one four-byte binary relay frame."""
    if channel not in (*range(1, 9), ALL_CHANNELS):
        raise RelayProtocolError("channel must be 1-8 or 0x0F")
    if operation not in (OP_OFF, OP_ON, OP_QUERY):
        raise RelayProtocolError("operation must be OFF(0), ON(1), or QUERY(2)")
    prefix = (START_BYTE, channel, operation)
    return bytes((*prefix, sum(prefix) & 0xFF))


CH1_ON = build_frame(1, OP_ON)
CH1_OFF = build_frame(1, OP_OFF)
CH1_QUERY = build_frame(1, OP_QUERY)
CH2_ON = build_frame(2, OP_ON)
CH2_OFF = build_frame(2, OP_OFF)
CH2_QUERY = build_frame(2, OP_QUERY)
ALL_OFF = build_frame(ALL_CHANNELS, OP_OFF)
ALL_QUERY = build_frame(ALL_CHANNELS, OP_QUERY)

_STATUS_PATTERN = re.compile(rb"CH([12]):(ON|OFF)(?:\r?\n|$)", re.IGNORECASE)


def parse_status_response(payload: bytes) -> dict[int, bool]:
    """Parse the ASCII response to ``ALL_QUERY``.

    A valid two-channel response must report both channels. Extra ASCII lines
    are tolerated so firmware revisions can add diagnostics without breaking
    the safety probe.
    """
    states: dict[int, bool] = {}
    for match in _STATUS_PATTERN.finditer(payload):
        channel = int(match.group(1))
        states[channel] = match.group(2).upper() == b"ON"
    if set(states) != {1, 2}:
        printable = payload.decode("ascii", errors="replace").strip()
        raise RelayProtocolError(
            "relay query did not return both CH1 and CH2 states: "
            f"{printable or '<empty>'}"
        )
    return states
