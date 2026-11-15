"""Update Electron's package-time dictionary digest, retaining active validation.

Supports only the observed build-27194 ARM64 framework layout. The 32-byte digest
is packaging metadata in __DATA_CONST,__asar_integrity, not an executable patch.
Reference: electron/shell/common/asar/integrity_digest.mm, digest-slot version 1.
"""
import hashlib
import re
import struct

from recovery import require

SENTINEL = b'AGbevlPCksUGKNL8TSn7wGmJEuJsXb2A'


def dictionary_digest(integrity):
    require(isinstance(integrity, dict) and bool(integrity), 'Missing integrity dictionary')
    digest = hashlib.sha256()
    for key in sorted(integrity):
        value = integrity[key]
        # Reviewed dictionary uses ASCII paths; avoid unreviewed Unicode sort rules.
        require(isinstance(key, str) and key.isascii() and key.startswith('Resources/')
                and '..' not in key.split('/') and isinstance(value, dict)
                and set(value) == {'algorithm', 'hash'} and value['algorithm'] == 'SHA256'
                and isinstance(value['hash'], str) and re.fullmatch('[a-f0-9]{64}', value['hash']),
                'Unsupported integrity dictionary')
        digest.update((key + value['algorithm'] + value['hash']).encode())
    return digest.digest()


def slot(data):
    require(len(data) >= 32, 'Truncated framework')
    magic, cpu, subtype, kind, count, size, flags, reserved = struct.unpack_from('<8I', data)
    require((magic, cpu, kind) == (0xfeedfacf, 0x100000c, 6) and
            0 < count < 1000 and 32 + size <= len(data), 'Unsupported framework layout')
    offset, found = 32, []
    for _ in range(count):
        require(offset + 8 <= 32 + size, 'Truncated framework command')
        command, length = struct.unpack_from('<II', data, offset)
        require(length >= 8 and length % 8 == 0 and offset + length <= 32 + size,
                'Invalid framework command')
        if command == 0x19:
            require(length >= 72, 'Truncated framework segment')
            _, _, segment, vm, vm_size, fileoff, filesize, _, _, nsects, _ = struct.unpack_from('<II16s4Q4I', data, offset)
            require(length == 72 + nsects * 80 and fileoff + filesize <= len(data),
                    'Invalid framework segment')
            for i in range(nsects):
                section = struct.unpack_from('<16s16sQQ8I', data, offset + 72 + i * 80)
                name, owner, address, extent, start = section[:5]
                if name.rstrip(b'\0') != b'__asar_integrity':
                    continue
                require(segment.rstrip(b'\0') == owner.rstrip(b'\0') == b'__DATA_CONST'
                        and extent == 66 and start >= 32 + size and start >= fileoff
                        and start + extent <= fileoff + filesize
                        and address == vm + start - fileoff and address - vm + extent <= vm_size
                        and section[7] == 0 and section[8] == 0,
                        'Unsupported integrity section')
                found.append(start)
        offset += length
    require(offset == 32 + size and len(found) == 1, 'Missing or duplicate integrity section')
    start = found[0]
    require(data[start:start+32] == SENTINEL and data[start+32:start+34] == b'\x01\x01',
            'Integrity validation is disabled or unsupported')
    return start


def update(data, old_integrity, new_integrity):
    start = slot(data)
    old_digest, new_digest = dictionary_digest(old_integrity), dictionary_digest(new_integrity)
    require(data[start+34:start+66] == old_digest, 'Existing native integrity digest differs')
    result = data[:start+34] + new_digest + data[start+66:]
    require(slot(result) == start and result[:start+34] == data[:start+34]
            and result[start+66:] == data[start+66:], 'Unplanned native mutation')
    return result, {'section_offset': start, 'digest_offset': start+34, 'digest_size': 32,
                    'used': 1, 'version': 1, 'before': old_digest.hex(), 'after': new_digest.hex()}


def verify(data, integrity):
    start = slot(data)
    require(data[start+34:start+66] == dictionary_digest(integrity), 'Native dictionary digest differs')
    return start
