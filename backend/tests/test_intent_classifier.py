"""Smoke tests for the intent-classifier JSON parser."""

from orchestrator.intent_classifier import parse_intent_from_llm_response


def test_parses_valid_json():
    raw = """
    ```json
    {
      "agents_needed": [
        {
          "agent_name": "inventory_specialist",
          "targeted_prompt": "How many pumps?",
          "reason": "User asked about inventory"
        }
      ],
      "requires_coordination": false,
      "user_intent_summary": "Pump inventory"
    }
    ```
    """
    result = parse_intent_from_llm_response(raw)
    assert result is not None
    assert result.requires_coordination is False
    assert len(result.agents_needed) == 1
    assert result.agents_needed[0].agent_name == "inventory_specialist"


def test_returns_none_on_garbage():
    assert parse_intent_from_llm_response("not json at all") is None


def test_handles_unterminated_json_without_crashing():
    """The previous fallback path raised TypeError on count mismatch."""
    result = parse_intent_from_llm_response('{"agents_needed": [], "requires_coordination": false, "user_intent_summary": "x"')
    # Either returns a parsed object (if repair succeeds) or None — but never raises.
    assert result is None or hasattr(result, "agents_needed")
