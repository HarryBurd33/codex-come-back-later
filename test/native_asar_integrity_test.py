"""Package-time digest regeneration, without launching or weakening Electron."""
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import native_asar_integrity as n


def dictionary(value):
    return {'Resources/app.asar': {'algorithm': 'SHA256', 'hash': value*64}}


def framework():
    header = struct.pack('<8I', 0xfeedfacf, 0x100000c, 0, 6, 1, 152, 0, 0)
    segment = struct.pack('<II16s4Q4I', 0x19, 152, b'__DATA_CONST', 4096, 4096, 256, 66, 3, 1, 1, 0)
    section = struct.pack('<16s16sQQ8I', b'__asar_integrity', b'__DATA_CONST', 4096, 66, 256, 0, 0, 0, 0, 0, 0, 0)
    return header + segment + section + bytes(72) + n.SENTINEL + b'\x01\x01' + n.dictionary_digest(dictionary('a'))


class NativeIntegrityTest(unittest.TestCase):
    def test_only_digest_changes_and_active_validation_survives(self):
        original = framework(); changed, receipt = n.update(original, dictionary('a'), dictionary('b'))
        self.assertEqual(original[:290], changed[:290])
        self.assertEqual(original[322:], changed[322:])
        self.assertNotEqual(original[290:322], changed[290:322])
        self.assertEqual(n.verify(changed, dictionary('b')), 256)
        self.assertEqual((receipt['used'],receipt['version'],receipt['digest_size']), (1,1,32))

    def test_stale_or_corrupt_digest_is_rejected(self):
        with self.assertRaises(ValueError): n.update(framework(),dictionary('b'),dictionary('c'))
        with self.assertRaises(ValueError): n.verify(framework(),dictionary('b'))
        bad=bytearray(framework());bad[-1]^=1
        with self.assertRaises(ValueError): n.update(bytes(bad),dictionary('a'),dictionary('b'))

    def test_disabled_or_unknown_slot_version_is_not_enabled_or_bypassed(self):
        for flags in (b'\0\1',b'\1\2',b'\0\0'):
            bad=bytearray(framework());bad[288:290]=flags
            with self.assertRaises(ValueError):n.update(bytes(bad),dictionary('a'),dictionary('b'))

    def test_bad_section_extent_owner_and_architecture_are_rejected(self):
        for offset,value in ((4,0x1000007),(32+72+48,400),(32+72+60,1),(32+72+64,0x80000000)):
            bad=bytearray(framework());struct.pack_into('<I',bad,offset,value)
            with self.assertRaises(ValueError):n.slot(bytes(bad))
        with self.assertRaises(ValueError): n.slot(framework()[:-1])
        bad=bytearray(framework());bad[32+8:32+24]=b'__TEXT'.ljust(16,b'\0')
        with self.assertRaises(ValueError):n.slot(bytes(bad))

    def test_unsupported_dictionary_cannot_remove_integrity(self):
        for value in ({},{'Resources/app.asar':{'algorithm':'none','hash':'a'*64}},
                      {'Resources/../app.asar':{'algorithm':'SHA256','hash':'a'*64}},
                      {'Resources/app.asar':{'algorithm':'SHA256','hash':'invalid'}}):
            with self.assertRaises(ValueError):n.dictionary_digest(value)


if __name__ == '__main__': unittest.main()
