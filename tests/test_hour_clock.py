import unittest
from native.retail_clock import daylight,state_for_hour,profile_for_minute,clock_metadata


class HourClockTests(unittest.TestCase):
    def test_original_twilight_boundaries_and_hourly_states(self):
        self.assertEqual([daylight(m)for m in [329,330,360,389,390,1049,1050,1080,1109,1110]],
            [0,0,127,250,255,255,255,127,4,0])
        self.assertEqual([h for h in range(24)if state_for_hour(h)=='twilight'],[6,18])
        self.assertEqual([h for h in range(24)if state_for_hour(h)=='day'],list(range(7,18)))
        self.assertEqual(len(clock_metadata()['hours']),24)

    def test_twilight_uses_native_integer_arithmetic_before_rendering(self):
        plan=dict(lighting_profiles=dict(day=dict(ambient=30,ambient_rgb=[250,250,250]),
            night=dict(ambient=35,ambient_rgb=[75,100,255])))
        dawn=profile_for_minute(plan,360);dusk=profile_for_minute(plan,1080)
        self.assertEqual(dawn,dusk);self.assertEqual(dawn['ambient'],31)
        self.assertEqual(dawn['expected_native_ambient'],41);self.assertEqual(dawn['ambient_rgb'],[161,174,252])
        with self.assertRaises(ValueError):daylight(1440)

