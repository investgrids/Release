"""
Step 3.4D-3: the V2 specialist generation contract. The model is asked only for what it has authority to publish (sourced prose), is told to state each fact once as a verbatim claim, and is no longer
asked for verdicts, scores, scenarios or decision blocks. Model-free: prompts are built and a contract-conformant generation is run through the real validators and gates.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from app.api.companies import _NSE_UNIVERSE as UNIVERSE
from app.services.ai_search import answer_authorization as AA
from app.services.ai_search import conclusion_scope as SC
from app.services.ai_search import structured_authorization as SA
from app.services.ai_search import validation as V
from app.services.ai_search.schema import flatten_nested
from app.services.ai_search.specialists import company as company_spec
from app.services.ai_search.specialists import comparison as comparison_spec
from app.services.ai_search.specialists import sector as sector_spec
from app.services.ai_search.specialists.base import parse_specialist_json
from tests.services.test_ai_search_fail_closed import bundle, ent, news_row, ev_row  # noqa: F401
from tests.services.test_ai_search_structured_authorization import ENTS, QUERY, cc1_bundle  # noqa: F401

# Output keys the model has no authority to publish. Quoted, so prose words like "rating" inside an instruction do not count.
PROHIBITED_KEYS = ('"rating"', '"direction"', '"sentiment"', '"confidence"', '"confidence_self_rating"', '"verdict_scale"', '"scenarios"', '"probability"', '"impact_score"', '"impact_type"',
                   '"outlook"', '"positive"', '"score"', '"sector_score"', '"winner"', '"advantage"', '"decision_intelligence"', '"decision_engine_v2"', '"ai_conclusion"', '"current_view"',
                   '"investor_action_note"', '"opportunity_matrix"', '"risk_matrix"', '"top_picks"', '"best_investor_type"', '"entity_analyses"', '"holding_analysis"', '"near_term_outlook"',
                   '"immediate"', '"one_week"', '"one_to_three_months"', '"six_to_twelve_months"', '"one_to_three_years"', '"what_changes_the_view"', '"what_invalidates_the_thesis"',
                   '"explain_why_not"', '"best_for"', '"insights"', '"medium_term"', '"long_term"', '"what_priced_in"', '"immediate_impact"', '"horizon"', '"why"', '"money_flow"',
                   '"sector_leaders"', '"sector_laggards"')
KEPT_KEYS = ('"claim_sources"', '"summary"', '"bottom_line"', '"what_happened"', '"key_drivers"', '"companies"', '"sectors"', '"risks"', '"opportunities"', '"milestones"', '"monitoring"')


def _evidence():
    b = bundle("company", events=[ev_row("e1", "Infosys wins deal", ["INFY"])], news=[news_row("n1", "IT stocks rise")])
    b.context_lines = ["TCS: P/E 15.1, P/B 6.85"]
    return b


def prompts() -> dict[str, str]:
    ents2 = {"companies": ["TCS", "INFY"], "company_matches": [{"name": "Tata Consultancy Services", "symbol": "TCS"}, {"name": "Infosys", "symbol": "INFY"}], "sectors": [], "policies": []}
    ents3 = {"companies": ["TCS", "INFY", "WIPRO"], "company_matches": [{"name": "Tata Consultancy Services", "symbol": "TCS"}, {"name": "Infosys", "symbol": "INFY"}, {"name": "Wipro", "symbol": "WIPRO"}], "sectors": [], "policies": []}
    b2 = _evidence()
    b2.plan_kind = "comparison"
    sector_ev = bundle("topic", events=[ev_row("e1", "IT spending slows", ["TCS"])])
    sector_ev.sector_rows = [{"name": "IT", "value": "+1.7%"}]
    return {
        "company": company_spec.build_prompt("How is TCS doing?", _evidence(), {}, {"companies": ["TCS"], "company_matches": [], "sectors": [], "policies": []}),
        "pairwise": comparison_spec.build_prompt("TCS vs Infosys", b2, {"holding": "Tata Consultancy Services", "target": "Infosys", "is_comparison": True}, ents2),
        "multi": comparison_spec._build_multi_compare_prompt("Compare TCS, Infosys, Wipro", b2, ents3),
        "compact": comparison_spec._build_multi_compare_compact_prompt("Compare TCS, Infosys, Wipro", ["TCS", "Infosys", "Wipro"]),
        "sector": sector_spec.build_prompt("IT sector outlook", sector_ev, {}, {"companies": [], "company_matches": [], "sectors": ["it"], "policies": []}),
    }


PROMPTS = prompts()


@pytest.mark.parametrize("name", list(PROMPTS))
def test_no_specialist_prompt_requests_an_output_structure_the_model_cannot_publish(name):
    # the compact multi-compare retry's own success key is a per-entity prose view ("entity_analyses": view/strengths/risks), not the removed decision block
    present = [k for k in PROHIBITED_KEYS if k in PROMPTS[name] and not (name == "compact" and k == '"entity_analyses"')]
    assert present == [], (name, present)


@pytest.mark.parametrize("name", ["company", "pairwise", "multi", "sector"])
def test_the_prompts_still_request_the_grounded_prose_structures(name):
    missing = [k for k in KEPT_KEYS if k not in PROMPTS[name] and not (name == "multi" and k == '"monitoring"')]       # the multi-compare prompt omits extras by design (token budget)
    assert missing == [], (name, missing)


@pytest.mark.parametrize("name", ["company", "pairwise", "multi", "sector"])
def test_the_prompts_carry_the_canonical_claim_and_scope_rules(name):
    p = PROMPTS[name]
    assert "CANONICAL CLAIMS" in p and "repeat the IDENTICAL sentence word for word" in p and "never restate it in different words" in p
    assert "SCOPE: conclude only what the evidence covers" in p and "valuation multiples" in p and "do not say which company is stronger" in p
    assert "limitation, not a fact" in p
    assert "Never say Buy, Sell, Hold" in p and "do not give a verdict" in p
    assert "GROUNDING: use ONLY facts" in p


@pytest.mark.parametrize("name", ["company", "pairwise", "multi", "sector", "compact"])
def test_no_prompt_tells_the_model_to_name_a_winner_or_supply_outside_numbers(name):
    low = PROMPTS[name].lower()
    assert "use real nse symbols, actual rupee amounts" not in low and "basis to estimate" not in low
    assert "sum to exactly 100" not in low and "mirrors investment.verdict_scale" not in low


def test_prompts_are_materially_smaller_than_the_previous_contract():
    # measured against the pre-D-3 company prompt (about 6,900 characters of schema and rules before the evidence lists; recorded in the D-3 report)
    assert len(PROMPTS["company"]) < 6000


def test_the_removed_schema_groups_are_empty_so_no_caller_can_reintroduce_them():
    from app.services.ai_search import schema as S
    assert S.render_decision_group(True) == "" and S.render_decision_group(False) == "" and S.DECISION_GROUP == ""
    assert "verdict" not in S.INVESTMENT_GROUP.lower().replace("do not give a verdict", "")


# ── a contract-conformant generation: nested model output as the new prompt asks for it ──────────────────────────────────────────────────

V_SENT = "TCS is at P/E 15.1 and P/B 6.85, versus Infosys at P/E 13.3 and P/B 4.54."
R_SENT = "TCS's 52-week range is 1976.8-3350.0; Infosys's 52-week range is 980.4-1728.0."
TCS_SENT = 'TCS disclosed a press release dated 2026-10-01 titled "Best Buy s Global Capability Center in India to transition to TCS".'
INFY_SENT = "Infosys announced a strategic collaboration with Columbia University on 2026-10-01."
LIMIT = "Recent operating results for either company are not in the current evidence."


def conformant_raw(summary=V_SENT, bottom=V_SENT, what_happened=R_SENT, extra_claims=(), why="") -> str:
    claims = [{"claim": V_SENT, "sources": ["C1", "C2"]}, {"claim": R_SENT, "sources": ["C1", "C2"]}, {"claim": TCS_SENT, "sources": ["A2"]}, {"claim": INFY_SENT, "sources": ["A3"]}, *extra_claims]
    return json.dumps({
        "investment": {"summary": summary, "bottom_line": bottom},
        "claim_sources": claims,
        "evidence": {"what_happened": what_happened, "why_it_happened": why,
                     "key_drivers": [{"icon": "valuation", "title": "Valuation gap", "explanation": "The valuation gap noted above is the only comparison the evidence supports."}]},
        "companies": [{"symbol": "TCS", "name": "TCS", "reason": TCS_SENT}, {"symbol": "INFY", "name": "Infosys", "reason": INFY_SENT}],
        "sectors": [{"name": "Information Technology Services", "explanation": LIMIT}],
        "timeline": {"milestones": []},
        "risks": {"risks": [LIMIT], "opportunities": []},
        "extras": {"monitoring": {"items": [{"label": "Quarterly results", "importance": "critical", "why_it_matters": "They would settle the open operating question.", "frequency": "Every 3 months"}]},
                   "follow_up_questions": ["How do their operating results compare once reported?"]},
    })


def test_a_conformant_generation_parses_and_the_unrequested_fields_are_absent_not_neutral():
    parsed, degraded = parse_specialist_json(conformant_raw(), QUERY)
    assert degraded is False
    assert parsed["confidence"] is None and parsed["confidence_self_rating"] is None and parsed["sentiment"] is None
    v = parsed["investment_verdict"]
    assert v["rating"] is None and v["direction"] is None and v["confidence"] is None and v["horizon"] is None and v["top_picks"] == []
    assert parsed["decision_engine_v2"] == {} and parsed["scenarios"] == {} and parsed["ai_conclusion"] == {} and parsed["timeline_intelligence"] == {} and parsed["opportunity_risk_matrix"] == {}


def test_validation_is_quiet_when_there_is_no_model_verdict_to_reconcile():
    parsed, _ = parse_specialist_json(conformant_raw(), QUERY)
    validated, report = V.validate_and_repair(parsed)
    assert report.grounding_collapsed is False and report.contradiction_flagged is False
    assert not any("verdict" in r or "rating" in r for r in report.repairs)


def test_a_conformant_generation_is_authorized_and_generated_no_structured_claims():
    parsed, _ = parse_specialist_json(conformant_raw(), QUERY)
    validated, _ = V.validate_and_repair(parsed)
    b = cc1_bundle()
    auth = AA.authorize(validated, b, ENTS, UNIVERSE, QUERY)
    assert auth["authorized"] is True and auth["reasons"] == [], auth
    scope = SC.assess(QUERY, {}, ENTS, b, UNIVERSE)
    assert scope["partial"] is True and SC.overreach(validated, scope) == []
    clean, withheld = SA.sanitize(validated)
    assert withheld == [], withheld          # nothing the model generated needed withholding: the contract no longer asks for it
    assert SA.public_summary(withheld)["state"] == "none_generated"


def test_repeating_a_claimed_sentence_verbatim_in_several_fields_is_covered_by_one_entry():
    parsed, _ = parse_specialist_json(conformant_raw(summary=V_SENT, bottom=V_SENT, what_happened=V_SENT, why=R_SENT), QUERY)
    validated, _ = V.validate_and_repair(parsed)
    assert AA.authorize(validated, cc1_bundle(), ENTS, UNIVERSE, QUERY)["authorized"] is True


def test_paraphrasing_a_claimed_fact_in_another_field_is_still_rejected_no_fuzzy_matching():
    para = "Infosys trades at a lower P/E of 13.3 and P/B of 4.54 than TCS at 15.1 and 6.85."
    parsed, _ = parse_specialist_json(conformant_raw(bottom=para), QUERY)
    validated, _ = V.validate_and_repair(parsed)
    auth = AA.authorize(validated, cc1_bundle(), ENTS, UNIVERSE, QUERY)
    assert auth["authorized"] is False and "uncovered_factual_sentences" in auth["reasons"]


def test_an_overall_winner_sentence_in_a_conformant_shape_still_fails_the_scope_check():
    win = "Infosys is the stronger company overall."
    parsed, _ = parse_specialist_json(conformant_raw(bottom=win, extra_claims=[{"claim": win, "sources": ["C1", "C2"]}]), QUERY)
    validated, _ = V.validate_and_repair(parsed)
    scope = SC.assess(QUERY, {}, ENTS, cc1_bundle(), UNIVERSE)
    assert SC.overreach(validated, scope) == [win]


def test_a_conformant_generation_reaches_the_public_response_without_any_withheld_structure(pipe_real):
    run_pipeline, pipe = pipe_real
    pipe["set_bundle"](cc1_bundle())
    parsed, _ = parse_specialist_json(conformant_raw(), QUERY)
    pipe["generation"] = (parsed, False)
    _raw, res, _ = run_pipeline("TCS vs Infosys, which is stronger? (3.4D-3 e2e)")
    assert res["synthesis_incomplete"] is False and res["answer_authorization"]["authorized"] is True
    assert res["structured_authorization"] == {"policy": "llm_structured_claims_withheld_unless_deterministically_authorized", "withheld": [], "state": "none_generated"}
    assert res["conclusion_scope"]["authorized"] == "valuation_comparison" and res["conclusion_scope"]["partial"] is True
    assert res["investment_verdict"]["rating"] == "Not Applicable" and res["investment_verdict"]["direction"] is None and res["answer"]["sentiment"] is None
    assert res["scenarios"] == {} and res["investment_verdict"]["engine_verdict"] is None
    assert V_SENT in res["answer"]["summary"] and any("valuation comparison only" in c for c in res["confidence_data"]["caveats"])


@pytest.fixture
def pipe_real(real_assembly):
    from tests.services.test_ai_search_fail_closed import run_pipeline
    return run_pipeline, real_assembly


from tests.services.test_ai_search_structured_authorization import real_assembly  # noqa: E402,F401
from tests.services.test_ai_search_fail_closed import pipe  # noqa: E402,F401
