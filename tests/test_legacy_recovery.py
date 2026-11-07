import struct
import unittest
from native.legacy_recovery import omit_unmapped_v1


def record(uid,x=24000,flags=1):
    return struct.pack('<hIBIiii',9,uid,0,flags,x,10000,0)+bytes(12)+bytes([0,100])+bytes(12)+(bytes(19)if flags&4 else b'')


class LegacyRecoveryTests(unittest.TestCase):
    def test_recovery_preserves_surviving_records_and_empty_slot_order(self):
        header=struct.pack('<4sii',b'MAP ',1,4)
        first=record(0x1234);unknown=record(0xabcdef,flags=5);last=record(0x5678,x=24100)
        raw=header+first+unknown+struct.pack('<h',-1)+last
        result,omitted=omit_unmapped_v1('41_23_9.dat',raw,{0xabcdef})
        self.assertEqual(result,header+first+struct.pack('<hh',-1,-1)+last)
        self.assertEqual(len(omitted),1);self.assertEqual(omitted[0]['slot'],1)
        self.assertEqual(omitted[0]['byte_range'],[12+len(first),12+len(first)+len(unknown)])

    def test_recovery_rejects_truncation_extra_bytes_and_other_versions(self):
        raw=struct.pack('<4sii',b'MAP ',1,1)+record(0x1234)
        for invalid in [raw[:-1],raw+b'junk',raw[:4]+struct.pack('<i',15)+raw[8:]]:
            with self.assertRaises(ValueError):omit_unmapped_v1('41_23_9.dat',invalid,{0x1234})
