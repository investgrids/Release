| ID | Type | UI mode (exp -> got) | Specialist (exp -> got) | Entities | Gate A | Premise | Conclusion scope | Model call | Outcome |
|---|---|---|---|---|---|---|---|---|---|
| CR1 | company_research | direct_company_research -> direct_company_research | company -> company | OK | SUFFICIENT/company_assessment | None | - | yes | SUFFICIENT |
| CR2 | company_research | direct_company_research -> direct_company_research | company -> company | n/a | INSUFFICIENT/company_assessment missing current_company_evidence | not_applicable | - | no | REFUSAL_GATE_A |
| CR3 | company_research | direct_company_research -> direct_company_research | company -> company | OK | SUFFICIENT/company_assessment | None | - | yes | SUFFICIENT |
| EI1 | event_impact | event_impact -> event_impact | company -> company | n/a | INSUFFICIENT/event_impact missing event_verification | not_established | - | no | REFUSAL_GATE_A |
| EI2 | event_impact | event_impact -> event_impact | company -> company | n/a | INSUFFICIENT/event_impact missing event_verification | not_established | - | no | REFUSAL_GATE_A |
| EI3 | event_impact | event_impact -> event_impact | company -> sector (diff) | OK | SUFFICIENT/sector_assessment | None | - | yes | SUFFICIENT |
| SR1 | sector_research | sector_theme_research -> sector_theme_research | sector -> sector | OK | SUFFICIENT/sector_assessment | None | - | yes | SUFFICIENT |
| SR2 | sector_research | sector_theme_research -> sector_theme_research | sector -> sector | OK | SUFFICIENT/sector_assessment | None | - | yes | SUFFICIENT |
| SR3 | sector_research | sector_theme_research -> sector_theme_research | sector -> sector | OK | SUFFICIENT/sector_scan | None | - | yes | SUFFICIENT |
| MP1 | macro_policy | policy_macro_impact -> policy_macro_impact | sector -> company (diff) | OK | SUFFICIENT/macro_transmission | None | - | yes | SUFFICIENT |
| MP2 | macro_policy | policy_macro_impact -> direct_company_research **DIFF** | company -> company | OK | SUFFICIENT/macro_transmission | None | - | yes | SUFFICIENT |
| MP3 | macro_policy | policy_macro_impact -> direct_company_research **DIFF** | sector -> company (diff) | OK | SUFFICIENT/macro_transmission | None | - | yes | SUFFICIENT |
| CC1 | company_comparison | company_comparison -> company_comparison | comparison -> comparison | OK | SUFFICIENT/comparison | None | overall_strength -> valuation_comparison | yes | SUFFICIENT_PARTIAL_SCOPE |
| CC2 | company_comparison | company_comparison -> company_comparison | comparison -> comparison | OK | SUFFICIENT/comparison | None | overall_strength -> valuation_comparison | yes | SUFFICIENT_PARTIAL_SCOPE |
| CC3 | company_comparison | switch_analysis -> switch_analysis | comparison -> comparison | OK | SUFFICIENT/comparison | None | overall_strength -> valuation_comparison | yes | SUFFICIENT_PARTIAL_SCOPE |
| GE1 | general_explanation | direct_company_research -> direct_company_research | company -> company | OK | SUFFICIENT/not_gated | None | - | yes | NOT_GATED_EDUCATION_OR_GENERAL |
| GE2 | general_explanation | direct_company_research -> direct_company_research | company -> company | OK | SUFFICIENT/not_gated | None | - | yes | NOT_GATED_EDUCATION_OR_GENERAL |
| GE3 | general_explanation | direct_company_research -> direct_company_research | company -> company | OK | SUFFICIENT/not_gated | None | - | yes | NOT_GATED_EDUCATION_OR_GENERAL |
