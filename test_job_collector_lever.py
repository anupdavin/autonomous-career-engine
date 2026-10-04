import unittest

from lever_postings import parse_lever_posting


class LeverPostingParserTests(unittest.TestCase):
    def setUp(self):
        self.posting = {
            "id": "ff6eacff-741a-4f60-aff4-a45e89b003a9",
            "text": "Senior Software Engineer - Backend and AI Enabled",
            "categories": {"location": "India", "allLocations": ["India"]},
            "workplaceType": "remote",
            "hostedUrl": "https://jobs.lever.co/everbridge/ff6eacff-741a-4f60-aff4-a45e89b003a9",
            "descriptionPlain": "Full time remote role. Build Java and Spring Boot backend services.",
        }

    def test_remote_india_engineering_posting_is_normalized_with_evidence(self):
        result = parse_lever_posting(self.posting, "everbridge", "Everbridge")

        self.assertIsNotNone(result)
        self.assertEqual(result["company"], "Everbridge")
        self.assertEqual(result["location"], "India, Remote")
        self.assertEqual(result["work_location_status"], "VERIFIED")
        self.assertIn("India", result["work_location_evidence"])
        self.assertTrue(result["url"].startswith("https://jobs.lever.co/everbridge/"))

    def test_hybrid_posting_is_rejected_even_with_india_location(self):
        self.posting["workplaceType"] = "hybrid"

        self.assertIsNone(parse_lever_posting(self.posting, "everbridge", "Everbridge"))

    def test_non_india_remote_posting_is_rejected(self):
        self.posting["categories"]["location"] = "United States"
        self.posting["categories"]["allLocations"] = ["United States"]

        self.assertIsNone(parse_lever_posting(self.posting, "everbridge", "Everbridge"))

    def test_non_engineering_remote_posting_is_not_a_target(self):
        self.posting["text"] = "Remote Customer Success Manager"

        self.assertIsNone(parse_lever_posting(self.posting, "everbridge", "Everbridge"))


class InitialLifecycleTriageTests(unittest.TestCase):
    def test_recommendation_stays_shortlisted(self):
        from oracle_memory import initial_lifecycle_stage

        self.assertEqual(initial_lifecycle_stage("RECOMMENDED", 82, "NEEDS_REVIEW"), "SHORTLISTED")

    def test_verified_borderline_role_is_kept_for_human_review(self):
        from oracle_memory import initial_lifecycle_stage

        self.assertEqual(initial_lifecycle_stage("SKIPPED_LOW_MATCH", 64, "VERIFIED"), "SHORTLISTED")

    def test_low_score_or_unverified_borderline_role_stays_out_of_shortlist(self):
        from oracle_memory import initial_lifecycle_stage

        self.assertEqual(initial_lifecycle_stage("SKIPPED_LOW_MATCH", 59, "VERIFIED"), "DEAD_ZONE")
        self.assertEqual(initial_lifecycle_stage("SKIPPED_LOW_MATCH", 64, "NEEDS_REVIEW"), "DEAD_ZONE")


if __name__ == "__main__":
    unittest.main()
