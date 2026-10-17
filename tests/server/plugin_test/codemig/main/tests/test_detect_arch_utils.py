import unittest
from plugin.codemig.main.detect_arch.detect_arch_utils import create_0_to_n


class TestDetectArchUtils(unittest.TestCase):

    def test_create_0_to_n(self):
        self.assertEqual(
            create_0_to_n("a", 10),
            ['a0', 'a1', 'a2', 'a3', 'a4', 'a5', 'a6', 'a7', 'a8', 'a9', 'a10'])


if __name__ == "__main__":
    unittest.main()
