"""Unit tests for the Orchestrator's column-routing post-processing logic
(sf_lib/orchestrator.py:split_by_domain). The routing *decision* itself is a
live Cortex COMPLETE call and isn't unit-testable without a real Snowflake
session — what's tested here is the code-level logic that runs on whatever
the model comes back with: filtering unknown agent keys, dropping columns
that were never actually in the upload, deduping, and force-propagating
_id-suffixed columns across every domain touched by this upload. None of
this requires changing orchestrator.py's architecture; it's exercised by
monkeypatching CortexAgent so no live call happens.
"""

from sf_lib import orchestrator


class _StubCortexAgent:
    """Drop-in replacement for sf_lib.cortex.CortexAgent that returns a
    canned response instead of making a real SNOWFLAKE.CORTEX.COMPLETE call.
    """

    response: dict = {}

    def __init__(self, session, system_instruction):
        pass

    def generate_json(self, prompt, schema):
        return type(self).response


def _patch_agent(monkeypatch, response: dict):
    _StubCortexAgent.response = response
    monkeypatch.setattr(orchestrator, "CortexAgent", _StubCortexAgent)


def test_basic_routing_assigns_columns_to_known_agents(monkeypatch):
    _patch_agent(
        monkeypatch,
        {
            "assignments": [
                {"agentKey": "customer_agent", "columns": ["name", "email"], "reasoning": "x"},
                {"agentKey": "order_agent", "columns": ["total_amount"], "reasoning": "x"},
            ],
            "unassignedColumns": [],
        },
    )
    result = orchestrator.split_by_domain(None, ["name", "email", "total_amount"], [])
    assert result == {"customer_agent": ["name", "email"], "order_agent": ["total_amount"]}


def test_unknown_agent_key_is_dropped(monkeypatch):
    _patch_agent(
        monkeypatch,
        {
            "assignments": [
                {"agentKey": "not_a_real_agent", "columns": ["name"], "reasoning": "x"},
                {"agentKey": "customer_agent", "columns": ["email"], "reasoning": "x"},
            ],
            "unassignedColumns": [],
        },
    )
    result = orchestrator.split_by_domain(None, ["name", "email"], [])
    assert "not_a_real_agent" not in result
    assert result == {"customer_agent": ["email"]}


def test_hallucinated_column_not_in_upload_is_dropped(monkeypatch):
    _patch_agent(
        monkeypatch,
        {
            "assignments": [
                {
                    "agentKey": "customer_agent",
                    "columns": ["email", "a_column_that_was_never_uploaded"],
                    "reasoning": "x",
                },
            ],
            "unassignedColumns": [],
        },
    )
    result = orchestrator.split_by_domain(None, ["email"], [])
    assert result == {"customer_agent": ["email"]}


def test_id_column_force_propagates_to_every_touched_domain(monkeypatch):
    """The model is only instructed to duplicate shared join keys, not
    guaranteed to — orchestrator.py forces it in code for every _id-suffixed
    column regardless of what the model actually assigned.
    """
    _patch_agent(
        monkeypatch,
        {
            "assignments": [
                {"agentKey": "customer_agent", "columns": ["customer_id", "name"], "reasoning": "x"},
                {"agentKey": "order_agent", "columns": ["total_amount"], "reasoning": "x"},
            ],
            "unassignedColumns": [],
        },
    )
    result = orchestrator.split_by_domain(
        None, ["customer_id", "name", "total_amount"], []
    )
    assert "customer_id" in result["customer_agent"]
    assert "customer_id" in result["order_agent"], "shared id column must reach every domain touched by this upload"


def test_id_column_not_duplicated_if_model_already_assigned_it(monkeypatch):
    _patch_agent(
        monkeypatch,
        {
            "assignments": [
                {"agentKey": "customer_agent", "columns": ["customer_id"], "reasoning": "x"},
                {"agentKey": "order_agent", "columns": ["customer_id", "total_amount"], "reasoning": "x"},
            ],
            "unassignedColumns": [],
        },
    )
    result = orchestrator.split_by_domain(None, ["customer_id", "total_amount"], [])
    assert result["order_agent"].count("customer_id") == 1


def test_agent_with_zero_valid_columns_is_dropped_entirely(monkeypatch):
    _patch_agent(
        monkeypatch,
        {
            "assignments": [
                {"agentKey": "customer_agent", "columns": ["a_column_that_was_never_uploaded"], "reasoning": "x"},
            ],
            "unassignedColumns": ["name"],
        },
    )
    result = orchestrator.split_by_domain(None, ["name"], [])
    assert result == {}
