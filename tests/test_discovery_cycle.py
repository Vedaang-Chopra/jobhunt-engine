"""Tests for Task 10: cycle runner + stopping rules (search_strategy/cycle.py)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from search_strategy.cycle import AuthWallError, load_policy, run_cycle
from search_strategy.memory import SearchMemory


def make_policy(**over):
    policy = {
        "batch_size": 1,
        "max_batches_per_mode": 3,
        "stop_rules": {
            "min_new_per_query": 1,
            "max_duplicate_rate": 0.8,
            "authwall_or_captcha": "stop",
        },
        "low_yield_threshold": 3,
    }
    policy.update(over)
    return policy


def fake_result(new=5, inspected=10, relevant=8):
    dupes = inspected - new
    return {
        "results_inspected": inspected,
        "relevant_results": relevant,
        "new_results": new,
        "duplicate_results": dupes,
        "companies_found": [],
        "roles_found": [],
    }


class TestDiscoveryCycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mem = SearchMemory(root=Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_two_batches_with_replan_between(self):
        """Second planner call must see state reflecting the first batch."""
        calls = []

        def planner_fn(mode, state, remaining_budget):
            calls.append({"mode": mode, "state": dict(state),
                          "remaining_budget": remaining_budget})
            return [{"mode": mode, "query": f"q{len(calls)}", "family": "f"}]

        def executor_fn(mode, row):
            return fake_result(new=5)

        summary = run_cycle(["jobs"], total_budget=5, planner_fn=planner_fn,
                            executor_fn=executor_fn, mem=self.mem,
                            policy=make_policy(max_batches_per_mode=2))
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["state"]["recent_queries"], [])
        # Second call's state reflects the first appended record.
        self.assertIn("q1", calls[1]["state"]["recent_queries"])
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["modes"]["jobs"]["queries_executed"], 2)

    def test_stop_on_duplicate_saturation(self):
        """Batch with duplicate_rate >= 0.8 stops that mode early; next mode still runs."""
        ran = {"b": False}

        def planner_fn(mode, state, remaining_budget):
            return [{"mode": mode, "query": f"{mode}-q", "family": "f"}]

        def executor_fn(mode, row):
            if mode == "a":
                return fake_result(new=0, inspected=9, relevant=0)
            ran["b"] = True
            return fake_result(new=5)

        summary = run_cycle(["a", "b"], total_budget=6, planner_fn=planner_fn,
                            executor_fn=executor_fn, mem=self.mem,
                            policy=make_policy())
        ma = summary["modes"]["a"]
        self.assertEqual(ma["queries_executed"], 1)
        self.assertEqual(ma["stopped_reason"], "duplicate_saturation")
        self.assertTrue(ran["b"])
        self.assertEqual(summary["status"], "completed")

    def test_two_zero_new_batches_stops_mode(self):
        """Two consecutive batches where every query had new==0 also stops the mode."""
        def planner_fn(mode, state, remaining_budget):
            return [{"mode": mode, "query": f"{mode}-{len(state['recent_queries'])}",
                     "family": "f"}]

        def executor_fn(mode, row):
            # inspected=0 keeps dup-rate rule out of the way so the two
            # consecutive zero-new-batches rule is what triggers.
            return {"results_inspected": 0, "relevant_results": 1,
                    "new_results": 0, "duplicate_results": 0,
                    "companies_found": [], "roles_found": []}

        summary = run_cycle(["a"], total_budget=6, planner_fn=planner_fn,
                            executor_fn=executor_fn, mem=self.mem,
                            policy=make_policy())
        ma = summary["modes"]["a"]
        self.assertEqual(ma["queries_executed"], 2)
        self.assertEqual(ma["stopped_reason"], "zero_new_two_batches")

    def test_stop_on_authwall(self):
        """AuthWallError stops everything immediately."""
        ran = {"after": []}

        def planner_fn(mode, state, remaining_budget):
            return [{"mode": mode, "query": f"{mode}-q", "family": "f"}]

        def executor_fn(mode, row):
            if mode == "a" and not ran["after"]:
                raise AuthWallError("linkedin authwall")
            ran["after"].append(row["query"])
            return fake_result()

        summary = run_cycle(["a", "b"], total_budget=6, planner_fn=planner_fn,
                            executor_fn=executor_fn, mem=self.mem,
                            policy=make_policy())
        self.assertEqual(summary["status"], "stopped_authwall")
        self.assertEqual(ran["after"], [])  # no execution after the wall

    def test_budget_not_exceeded(self):
        execs = []

        def planner_fn(mode, state, remaining_budget):
            return [{"mode": mode, "query": f"{mode}-{len(execs)}", "family": "f"}]

        def executor_fn(mode, row):
            execs.append(row["query"])
            return fake_result(new=5)

        summary = run_cycle(["a", "b"], total_budget=5, planner_fn=planner_fn,
                            executor_fn=executor_fn, mem=self.mem,
                            policy=make_policy())
        self.assertLessEqual(len(execs), 5)
        self.assertEqual(summary["budget_used"], len(execs))

    def test_dry_run_prints_plan_only(self):
        def planner_fn(mode, state, remaining_budget):
            return [{"mode": mode, "query": f"{mode}-plan", "family": "f"}]

        def executor_fn(mode, row):  # pragma: no cover - must never run
            raise AssertionError("executor called during dry_run")

        summary = run_cycle(["jobs", "posts"], total_budget=6, planner_fn=planner_fn,
                            executor_fn=executor_fn, mem=self.mem,
                            policy=make_policy(), dry_run=True)
        self.assertEqual(summary["budget_used"], 0)
        plan = summary["plan"]
        self.assertEqual(len(plan), 2)
        self.assertEqual(plan["jobs"][0]["query"], "jobs-plan")
        json.dumps(summary)  # summary must be JSON-serializable

    def test_adaptive_reallocation_shifts_leftover(self):
        """Mode 'a' saturates immediately; its leftover shifts to high-yield mode 'b'."""
        budgets = {"a": [], "b": []}

        def planner_fn(mode, state, remaining_budget):
            budgets[mode].append(remaining_budget)
            return [{"mode": mode, "query": f"{mode}-q{len(budgets[mode])}",
                     "family": "f"}]

        def executor_fn(mode, row):
            if mode == "a":
                return fake_result(new=0, inspected=9, relevant=0)  # dup rate 1.0
            return fake_result(new=5)

        summary = run_cycle(["a", "b"], total_budget=4, planner_fn=planner_fn,
                            executor_fn=executor_fn, mem=self.mem,
                            policy=make_policy())
        # Equal split initially: 2 / 2; 'a' runs first and saturates after 1
        # query, so its leftover (2-1=1) is granted to 'b' before b's first
        # planner call -> b sees remaining budget 3 on its first call.
        self.assertEqual(budgets["a"], [2])
        self.assertEqual(budgets["b"], [3, 2, 1])
        self.assertEqual(summary["budget_used"], 4)


class TestLoadPolicy(unittest.TestCase):
    def test_load_policy_from_yaml(self):
        p = load_policy()
        self.assertIsInstance(p, dict)
        self.assertIn("stop_rules", p)
        self.assertIn("max_duplicate_rate", p["stop_rules"])

    def test_fallback_seed_when_missing(self):
        p = load_policy(path=Path("/nonexistent/search_policy.yaml"))
        self.assertEqual(p["max_batches_per_mode"], 3)
        self.assertAlmostEqual(p["mix_policy"]["proven"], 0.30)
        self.assertEqual(p["stop_rules"]["authwall_or_captcha"], "stop")


class TestCli(unittest.TestCase):
    def test_main_exit_3_when_planner_unavailable(self):
        import discovery_cycle
        rc = discovery_cycle.main(["--modes", "jobs", "--budget", "4", "--dry-run",
                                   "--data-root", tempfile.mkdtemp()])
        self.assertEqual(rc, 3)


if __name__ == "__main__":
    unittest.main()
