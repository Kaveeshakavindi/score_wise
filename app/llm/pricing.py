from __future__ import annotations

from dataclasses import dataclass

# Per-model $/token rates, used to turn a raw (input_tokens, output_tokens)
# pair into an estimated dollar cost for display (e.g. next to a generated
# tutor explanation) without re-deriving it from scratch at every call site.
#
# Only ever add a rate here from Anthropic's own published API pricing
# (https://www.anthropic.com/pricing -> API pricing table, $/MTok input and
# output -- NOT the Claude.ai consumer subscription price, which is a flat
# monthly fee unrelated to per-call API cost). estimate_cost_usd() returns
# None for any model not listed below, and callers must treat None as "cost
# unknown" (e.g. hide the cost line in the UI) rather than showing $0.00.
#
# Note: this doesn't account for prompt-caching write/read rates (currently
# $2.50 / $0.20 per MTok for claude-sonnet-5) since the app doesn't use
# prompt caching yet -- every call is priced as plain input/output tokens.
# Revisit this table if that changes.


@dataclass(frozen=True)
class ModelPricing:
    """USD per 1,000,000 tokens, matching how providers publish rates."""

    input_per_million: float
    output_per_million: float


MODEL_PRICING: dict[str, ModelPricing] = {
    # https://www.anthropic.com/pricing, confirmed 2026-08-28.
    "claude-sonnet-5": ModelPricing(input_per_million=2.00, output_per_million=10.00),
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Estimated dollar cost for one call, or None if `model` isn't in
    MODEL_PRICING -- never fabricates a number for an unlisted/unknown model."""
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        return None
    return (input_tokens / 1_000_000) * pricing.input_per_million + (
        output_tokens / 1_000_000
    ) * pricing.output_per_million
