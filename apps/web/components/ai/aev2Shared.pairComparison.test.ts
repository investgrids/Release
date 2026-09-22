// Proves switch_analysis and comparison compute IDENTICAL dimension
// values for the same two companies — only the field NAMES differ
// between the two backend schemas (current_company/alternative_company
// vs left_company/right_company), never the underlying numbers. The
// real arithmetic equivalence is proven server-side (test_comparison_
// assembly.py's test_switch_and_comparison_compute_identical_
// dimensions_for_the_same_two_companies, since both call the SAME
// pair_comparison.py builder) — this test proves the FRONTEND'S two
// adapters (switchDimensionsToPairViews/comparisonDimensionsToPairViews)
// produce the same neutral shape for equivalent input, so neither
// layout could silently drift by misreading its own schema's fields.
import { describe, it, expect } from "vitest";
import { switchDimensionsToPairViews, comparisonDimensionsToPairViews } from "./aev2Shared";
import type { AEV2ComparisonDimension, AEV2PairComparisonDimension } from "./aev2Types";

describe("switchDimensionsToPairViews / comparisonDimensionsToPairViews", () => {
  it("produce the same neutral PairDimensionView for equivalent left/right data", () => {
    const leftValue = { display: "285.40 (+1.10%)", evidence_refs: [] };
    const rightValue = { display: "4,512.00 (-0.30%)", evidence_refs: [] };

    const switchDim: AEV2ComparisonDimension = {
      key: "price_reaction", label: "Price reaction",
      current_company: leftValue, alternative_company: rightValue,
      evidence_refs: [], comparable: true,
    };
    const comparisonDim: AEV2PairComparisonDimension = {
      key: "price_reaction", label: "Price reaction",
      left_company: leftValue, right_company: rightValue,
      evidence_refs: [], comparable: true,
    };

    const [switchView] = switchDimensionsToPairViews([switchDim]);
    const [comparisonView] = comparisonDimensionsToPairViews([comparisonDim]);

    expect(switchView).toEqual(comparisonView);
  });

  it("preserve comparable=false and unavailable_reason identically across both schemas", () => {
    const switchDim: AEV2ComparisonDimension = {
      key: "recent_developments", label: "Recent developments",
      current_company: null, alternative_company: null,
      evidence_refs: [], comparable: false,
      unavailable_reason: "No company-attributed development found for HAL",
    };
    const comparisonDim: AEV2PairComparisonDimension = {
      key: "recent_developments", label: "Recent developments",
      left_company: null, right_company: null,
      evidence_refs: [], comparable: false,
      unavailable_reason: "No company-attributed development found for HAL",
    };

    const [switchView] = switchDimensionsToPairViews([switchDim]);
    const [comparisonView] = comparisonDimensionsToPairViews([comparisonDim]);

    expect(switchView).toEqual(comparisonView);
  });
});
