import unittest

from job_sources import GREENHOUSE_BOARDS, LEVER_BOARDS


class JobSourceConfigurationTests(unittest.TestCase):
    def test_current_official_target_boards_are_configured(self):
        boards = dict(GREENHOUSE_BOARDS)

        self.assertEqual(boards["oportun"], "Oportun")
        self.assertEqual(boards["eltropyinc"], "Eltropy")

    def test_board_slugs_are_unique(self):
        slugs = [slug for slug, _ in GREENHOUSE_BOARDS]

        self.assertEqual(len(slugs), len(set(slugs)))

    def test_lever_boards_include_live_remote_india_targets(self):
        boards = dict(LEVER_BOARDS)

        self.assertEqual(boards["everbridge"], "Everbridge")
        self.assertEqual(boards["lingarogroup"], "Lingaro")
        self.assertEqual(boards["gohighlevel"], "HighLevel")
        self.assertEqual(len(boards), len(LEVER_BOARDS))


if __name__ == "__main__":
    unittest.main()
