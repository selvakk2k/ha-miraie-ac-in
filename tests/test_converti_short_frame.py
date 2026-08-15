"""Unit test verifying Short-Frame IR code generation for Powerful, Display, Clean, and Converti steps."""
import unittest

from tests.ha_stub import setup_ha_stubs
setup_ha_stubs()


class TestShortFrameIRGeneration(unittest.TestCase):
    def test_short_frame_byte_mapping(self):
        from custom_components.miraie_in.panasonic_ac_models.ir import generate_ir_code

        # Test Powerful
        res_p = generate_ir_code(mode="powerful")
        self.assertEqual(res_p["ahea_hex"], "0x0220E004000000060220E00480863541")

        # Test Display
        res_d = generate_ir_code(mode="display")
        self.assertEqual(res_d["ahea_hex"], "0x0220E004000000060220E004809E3256")

        # Test Clean
        res_c = generate_ir_code(mode="clean")
        self.assertEqual(res_c["ahea_hex"], "0x0220E004000000060220E00480CBF243")

        # Test Converti 110%
        res_c110 = generate_ir_code(mode="converti_110")
        self.assertEqual(res_c110["ahea_hex"], "0x0220E004000000060220E0048001AA31")

        # Test Converti 80%
        res_c80 = generate_ir_code(mode="converti_80")
        self.assertEqual(res_c80["ahea_hex"], "0x0220E004000000060220E0048004AA34")

        # Test Converti 40%
        res_c40 = generate_ir_code(mode="converti_40")
        self.assertEqual(res_c40["ahea_hex"], "0x0220E004000000060220E0048007AA37")


if __name__ == "__main__":
    unittest.main()
