"""Conservative build-27194 diagnostic: compare Mach-O bytes outside signature storage.

Uses native codesign separately for actual signature validity. Unsupported layouts stop
the development build; this parser never edits code and is not part of the application.
"""
import hashlib
import struct
import recovery as r


def thin(data):
    r.require(len(data) >= 32, 'Truncated Mach-O')
    magic, cpu, subtype, kind, count, size, flags, reserved = struct.unpack_from('<8I', data)
    r.require(magic == 0xfeedfacf and cpu in (0x100000c, 0x1000007) and kind in (2, 6, 8)
              and 0 < count < 1000 and 32 + size <= len(data), 'Unsupported Mach-O')
    offset, signature, linkedit = 32, None, None
    for _ in range(count):
        r.require(offset + 8 <= 32 + size, 'Truncated load command')
        command, length = struct.unpack_from('<II', data, offset)
        r.require(length >= 8 and length % 8 == 0 and offset + length <= 32 + size,
                  'Invalid load command')
        if command == 0x1d:
            r.require(signature is None and length == 16, 'Invalid signature command')
            signature = (offset, *struct.unpack_from('<II', data, offset + 8))
        if command == 0x19 and length >= 72 and data[offset+8:offset+24].rstrip(b'\0') == b'__LINKEDIT':
            r.require(linkedit is None, 'Duplicate linkedit')
            linkedit = offset
        offset += length
    r.require(offset == 32 + size and signature is not None and linkedit is not None,
              'Missing signature/linkedit index')
    command, start, length = signature
    _, vmsize, fileoff, filesize = struct.unpack_from('<4Q', data, linkedit + 24)
    r.require(start >= 32 + size and start % 16 == 0 and length > 0 and start + length == len(data)
              and fileoff <= start and fileoff + filesize == len(data) and vmsize >= filesize,
              'Unsupported signature/linkedit extent')
    # These are the only load-command fields codesign may change in this policy.
    payload = bytearray(data[:start])
    payload[command+8:command+16] = bytes(8)
    payload[linkedit+32:linkedit+40] = bytes(8)
    payload[linkedit+48:linkedit+56] = bytes(8)
    return cpu, subtype, hashlib.sha256(payload).hexdigest()


def fingerprints(path):
    data = path.read_bytes()
    if data[:4] == b'\xcf\xfa\xed\xfe':
        cpu, subtype, digest = thin(data)
        return [[cpu, subtype, digest]]
    r.require(data[:4] == b'\xca\xfe\xba\xbe' and len(data) >= 8, 'Unsupported universal Mach-O')
    count = struct.unpack_from('>I', data, 4)[0]
    r.require(0 < count <= 8 and 8 + count * 20 <= len(data), 'Invalid universal index')
    result, spans = [], []
    for i in range(count):
        cpu, subtype, offset, size, alignment = struct.unpack_from('>5I', data, 8 + i * 20)
        r.require(alignment <= 30 and offset % (1 << alignment) == 0 and
                  offset >= 8 + count * 20 and offset + size <= len(data), 'Invalid architecture extent')
        observed_cpu, observed_subtype, digest = thin(data[offset:offset+size])
        r.require((observed_cpu, observed_subtype) == (cpu, subtype), 'Architecture identity mismatch')
        result.append([cpu, subtype, digest])
        spans.append((offset, offset + size))
    ordered = sorted(spans)
    r.require(all(a[1] <= b[0] for a,b in zip(ordered, ordered[1:])) and
              len({tuple(v[:2]) for v in result}) == count, 'Overlapping or duplicate architectures')
    return result
