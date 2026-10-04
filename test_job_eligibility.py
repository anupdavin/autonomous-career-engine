import unittest

from eligibility import global_remote_evidence


class GlobalRemoteEligibilityTests(unittest.TestCase):
    def test_global_remote_location_is_accepted(self):
        evidence = global_remote_evidence("Remote - US", "")
        self.assertEqual(evidence, "Posting location: Remote - US")

    def test_global_remote_excerpt_is_preserved(self):
        evidence = global_remote_evidence(
            "",
            "This position is remote from US. Applicants should apply online.",
        )
        self.assertEqual(evidence, "Official posting excerpt: This position is remote from US")

    def test_global_location_combines_with_explicit_full_remote_text(self):
        evidence = global_remote_evidence("US", "Senior Backend Engineer | 100% Remote")
        self.assertEqual(
            evidence,
            "Posting location: US; official posting excerpt: Senior Backend Engineer | 100% Remote",
        )

    def test_oportun_official_remote_global_location_is_accepted(self):
        evidence = global_remote_evidence("Remote - US", "Senior Software Engineer (R14037)")

        self.assertEqual(evidence, "Posting location: Remote - US")

    def test_eltropy_global_location_and_full_remote_description_are_accepted(self):
        evidence = global_remote_evidence(
            "US",
            "Senior Backend Engineer |100% Remote| backend systems and APIs.",
        )

        self.assertTrue(evidence)
        self.assertIn("100% Remote", evidence)

    def test_worldwide_contractor_role_is_accepted(self):
        evidence = global_remote_evidence(
            "",
            "Remote worldwide. Engagement is through an independent contractor agreement.",
        )
        self.assertTrue(evidence)

    def test_explicit_relocation_exclusion_overrides_worldwide_remote(self):
        evidence = global_remote_evidence(
            "",
            "Remote worldwide. Must relocate to office.",
        )
        self.assertEqual(evidence, "")

    def test_singapore_location_is_rejected(self):
        evidence = global_remote_evidence(
            "Singapore",
            "This role is remote.",
        )
        self.assertEqual(evidence, "")

    def test_singapore_description_is_rejected(self):
        evidence = global_remote_evidence(
            "",
            "Remote worldwide, but must reside in singapore.",
        )
        self.assertEqual(evidence, "")

    def test_hybrid_location_is_rejected(self):
        evidence = global_remote_evidence("Remote US, hybrid", "")
        self.assertEqual(evidence, "")

    def test_required_hybrid_schedule_is_rejected(self):
        evidence = global_remote_evidence(
            "Remote - US",
            "The working arrangement requires a hybrid schedule.",
        )
        self.assertEqual(evidence, "")

    def test_posting_that_denies_full_remote_status_is_rejected(self):
        evidence = global_remote_evidence("US", "This is not a 100% remote role.")
        self.assertEqual(evidence, "")

    def test_onsite_days_are_rejected(self):
        evidence = global_remote_evidence(
            "Remote - US",
            "Applicants must work 2 days per week onsite.",
        )
        self.assertEqual(evidence, "")

    def test_no_onsite_requirement_does_not_reject_remote_role(self):
        evidence = global_remote_evidence(
            "",
            "Applicants may work remotely. No onsite attendance is required.",
        )
        self.assertIn("work remotely", evidence)

    def test_unrelated_negation_does_not_reject_global_role(self):
        evidence = global_remote_evidence(
            "Remote - US",
            "We do not discriminate based on age or nationality.",
        )
        self.assertEqual(evidence, "Posting location: Remote - US")


if __name__ == "__main__":
    unittest.main()
