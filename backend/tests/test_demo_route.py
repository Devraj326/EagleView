import unittest
from unittest.mock import patch

from app.routers import datasets


class DemoRouteTest(unittest.TestCase):
    def test_seed_endpoint_calls_pipeline(self):
        results = [{"name": "Orders", "status": "READY", "error": None}]
        session, ctx, user = object(), {"schema": "TEST"}, object()
        with patch.object(datasets.snowpark_service, "ready_context", return_value=(session, ctx)), \
             patch.object(datasets.demo_seed, "seed_demo_datasets", return_value=results) as seed:
            response = datasets.seed_demo_endpoint(user)
        seed.assert_called_once_with(session, ctx)
        self.assertEqual(response["results"], results)
        self.assertEqual(response["agent_log"], [])


if __name__ == "__main__":
    unittest.main()
