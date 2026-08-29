from __future__ import annotations

from app.llm.pricing import MODEL_PRICING, ModelPricing, estimate_cost_usd


def test_estimate_cost_usd_computes_from_the_pricing_table(monkeypatch) -> None:
    monkeypatch.setitem(
        MODEL_PRICING, "test-model", ModelPricing(input_per_million=3.0, output_per_million=15.0)
    )

    cost = estimate_cost_usd("test-model", input_tokens=1_000_000, output_tokens=500_000)

    assert cost == 3.0 + 7.5


def test_estimate_cost_usd_returns_none_for_an_unlisted_model() -> None:
    assert estimate_cost_usd("some-model-not-in-the-table", input_tokens=100, output_tokens=50) is None


def test_estimate_cost_usd_zero_tokens_is_zero_not_none(monkeypatch) -> None:
    monkeypatch.setitem(
        MODEL_PRICING, "test-model", ModelPricing(input_per_million=3.0, output_per_million=15.0)
    )

    assert estimate_cost_usd("test-model", input_tokens=0, output_tokens=0) == 0.0
