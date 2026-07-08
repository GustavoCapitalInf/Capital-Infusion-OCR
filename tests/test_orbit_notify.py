import unittest
from unittest.mock import patch, MagicMock

from utils.orbit_notify import notify_orbit


def _job_data(status="complete", qualifying_lenders=None, lender_evaluations=None):
    return {
        "status": status,
        "timestamp": "2026-07-01T19:52:33.196182+00:00",
        "applicant": {"monthly_revenue": 43703.11, "fico": 680},
        "bank_statement_metrics": {"nsf_count": 12, "avg_daily_balance": 3752.13},
        "lender_evaluations": lender_evaluations if lender_evaluations is not None else [
            {
                "code": "Fund So Fast",
                "full_name": "Fund So Fast",
                "overall": "QUALIFIES",
                "criteria": [
                    {"name": "Industry Restriction", "result": "PASS"},
                    {"name": "Monthly Revenue", "result": "PASS"},
                    {"name": "FICO", "result": "PASS"},
                    {"name": "NSFs", "result": "FAIL"},
                ],
            },
            {
                "code": "Idea",
                "full_name": "Idea Financial",
                "overall": "DOES_NOT_QUALIFY",
                "criteria": [
                    {"name": "Industry Restriction", "result": "PASS"},
                    {"name": "NSFs", "result": "FAIL"},
                ],
            },
        ],
        "qualifying_lenders": qualifying_lenders if qualifying_lenders is not None else [
            {
                "rank": 1,
                "code": "Fund So Fast",
                "full_name": "Fund So Fast",
                "summary": "Fund So Fast is an excellent fit.",
            },
        ],
    }


class NotifyOrbitTests(unittest.TestCase):
    @patch("utils.orbit_notify.requests.post")
    def test_skips_when_status_not_complete(self, mock_post):
        result = notify_orbit("CLIENT123", _job_data(status="pending"))
        self.assertEqual(result, {})
        mock_post.assert_not_called()

    @patch("utils.orbit_notify.requests.post")
    def test_skips_when_no_qualifying_lenders(self, mock_post):
        result = notify_orbit("CLIENT123", _job_data(qualifying_lenders=[]))
        self.assertEqual(result, {})
        mock_post.assert_not_called()

    @patch("utils.orbit_notify.requests.post")
    def test_builds_payload_and_posts(self, mock_post):
        mock_post.return_value = MagicMock(ok=True, status_code=200)
        job_data = _job_data()

        result = notify_orbit("CLIENT123", job_data)

        self.assertEqual(result, {"orbit_notified": True, "orbit_status": 200})
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertEqual(
            mock_post.call_args.args[0],
            "https://orbit-technology.com/api/ocr/results",
        )
        self.assertEqual(
            kwargs["headers"]["x-api-key"],
            "orbit-api-k_9f3d7a2b1c8e4f6d0a5b7c9e2f4a6d8b",
        )
        self.assertEqual(kwargs["timeout"], 10)

        payload = kwargs["json"]
        self.assertEqual(payload["clientId"], "CLIENT123")
        self.assertEqual(payload["analyzedAt"], "2026-07-01T19:52:33.196182+00:00")
        self.assertEqual(
            payload["matched_lenders"],
            [{"lender": "Fund So Fast", "match_score": 75, "reason": "Fund So Fast is an excellent fit."}],
        )
        self.assertEqual(
            payload["results"]["summary"],
            {
                "applicant": {"monthly_revenue": 43703.11, "fico": 680},
                "bank_statement_metrics": {"nsf_count": 12, "avg_daily_balance": 3752.13},
            },
        )
        self.assertEqual(payload["results"]["lenders"], job_data["lender_evaluations"])

    @patch("utils.orbit_notify.requests.post")
    def test_match_score_none_when_no_matching_evaluation(self, mock_post):
        mock_post.return_value = MagicMock(ok=True, status_code=200)
        job_data = _job_data(
            qualifying_lenders=[
                {"rank": 1, "code": "Ghost Lender", "full_name": "Ghost Lender", "summary": "N/A"},
            ],
        )

        notify_orbit("CLIENT123", job_data)

        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(
            payload["matched_lenders"],
            [{"lender": "Ghost Lender", "match_score": None, "reason": "N/A"}],
        )

    @patch("utils.orbit_notify.requests.post", side_effect=ConnectionError("boom"))
    def test_returns_not_notified_on_exception(self, mock_post):
        result = notify_orbit("CLIENT123", _job_data())
        self.assertEqual(result, {"orbit_notified": False, "orbit_status": "boom"})


if __name__ == "__main__":
    unittest.main()
