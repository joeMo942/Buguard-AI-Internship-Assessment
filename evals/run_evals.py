import asyncio
import json
from datetime import datetime
from app.ai.chains import run_nl_query_chain, run_risk_scoring_chain, run_enrichment_chain, run_report_chain
from app.ai.llm import get_llm
from app.ai.guardrails import validate_asset_references
from app.schemas.analysis import QueryFilter, RiskScoreResponse, EnrichmentResponse

# We need a real DB session for the data-dependent chains
from app.database import async_session_maker
from app.services.import_service import process_import

SEED_DATA = [
    {"id": "eval-d1", "type": "domain", "value": "evaltest.com", "status": "active", "source": "scan", "tags": ["root"]},
    {"id": "eval-s1", "type": "subdomain", "value": "api.evaltest.com", "status": "active", "source": "scan", "tags": ["prod"], "parent": "eval-d1"},
    {"id": "eval-c1", "type": "certificate", "value": "CN=api.evaltest.com", "status": "active", "source": "scan", 
     "metadata": {"issuer": "Let's Encrypt", "expires": "2024-01-01"}, "covers": "eval-s1"},
    {"id": "eval-ip1", "type": "ip_address", "value": "10.0.0.1", "status": "stale", "source": "scan", "tags": ["internal"]},
    {"id": "eval-svc1", "type": "service", "value": "22/tcp", "status": "active", "source": "scan", 
     "metadata": {"banner": "OpenSSH 7.2"}, "runs_on": "eval-ip1"},
]


async def seed_eval_data():
    async with async_session_maker() as db:
        await process_import(db, SEED_DATA, org_id="eval-org")


async def run_evals():
    results = {"timestamp": datetime.utcnow().isoformat(), "suites": {}}
    
    # Seed data first
    await seed_eval_data()
    
    # === Suite 1: NL Query Parsing (no DB needed) ===
    print("\n[Suite 1] NL Query Parsing")
    llm = get_llm(temperature=0.0)
    structured_llm = llm.with_structured_output(QueryFilter)
    from app.ai.prompts import nl_query_prompt
    chain = nl_query_prompt | structured_llm

    nl_test_cases = [
        {"input": "Show me all active domains", "expected": {"types": ["domain"], "statuses": ["active"], "is_ambiguous": False}},
        {"input": "Find stale certificates", "expected": {"types": ["certificate"], "statuses": ["stale"], "is_ambiguous": False}},
        {"input": "What's the weather like?", "expected": {"is_ambiguous": True}},
        {"input": "Show me everything tagged as prod", "expected": {"tags": ["prod"], "is_ambiguous": False}},
    ]
    
    passed_s1 = 0
    for tc in nl_test_cases:
        try:
            result = await chain.ainvoke({"user_input": tc["input"]})
            rd = result.model_dump(exclude_unset=True)
            if all(rd.get(k) == v for k, v in tc["expected"].items()):
                passed_s1 += 1
                print(f"  ✅ '{tc['input']}'")
            else:
                print(f"  ❌ '{tc['input']}' → got {rd}")
        except Exception as e:
            print(f"  💥 '{tc['input']}' → {e}")
    results["suites"]["nl_query"] = {"passed": passed_s1, "total": len(nl_test_cases)}

    # === Suite 2: Risk Scoring (requires DB) ===
    print("\n[Suite 2] Risk Scoring")
    risk_cases = [
        {"asset_id": "eval-c1", "check": lambda r: r.risk_score >= 6, "label": "Expired cert should be high risk"},
        {"asset_id": "eval-d1", "check": lambda r: 1 <= r.risk_score <= 10, "label": "Domain should have valid score"},
        {"asset_id": "eval-svc1", "check": lambda r: len(r.findings) > 0, "label": "SSH service should have findings"},
    ]
    passed_s2 = 0
    async with async_session_maker() as db:
        for tc in risk_cases:
            try:
                result = await run_risk_scoring_chain(db, tc["asset_id"], org_id="eval-org")
                if tc["check"](result):
                    passed_s2 += 1
                    print(f"  ✅ {tc['label']} (score={result.risk_score})")
                else:
                    print(f"  ❌ {tc['label']} (score={result.risk_score}, findings={result.findings})")
            except Exception as e:
                print(f"  💥 {tc['label']} → {e}")
    results["suites"]["risk_scoring"] = {"passed": passed_s2, "total": len(risk_cases)}

    # === Suite 3: Enrichment Accuracy ===
    print("\n[Suite 3] Enrichment Accuracy")
    enrich_cases = [
        {"asset_id": "eval-s1", "check": lambda r: r.environment in ("prod", "production"), "label": "api.evaltest.com tagged 'prod' → env=prod"},
        {"asset_id": "eval-c1", "check": lambda r: r.category == "security", "label": "Certificate → category=security"},
    ]
    passed_s3 = 0
    async with async_session_maker() as db:
        for tc in enrich_cases:
            try:
                result = await run_enrichment_chain(db, tc["asset_id"], org_id="eval-org")
                if tc["check"](result):
                    passed_s3 += 1
                    print(f"  ✅ {tc['label']} (env={result.environment}, cat={result.category})")
                else:
                    print(f"  ❌ {tc['label']} (env={result.environment}, cat={result.category})")
            except Exception as e:
                print(f"  💥 {tc['label']} → {e}")
    results["suites"]["enrichment"] = {"passed": passed_s3, "total": len(enrich_cases)}

    # === Suite 4: Report Grounding ===
    print("\n[Suite 4] Report Grounding")
    async with async_session_maker() as db:
        try:
            report = await run_report_chain(db, org_id="eval-org")
            known_ids = {d["id"] for d in SEED_DATA}
            known_values = {d["value"] for d in SEED_DATA}
            validation = validate_asset_references(report, known_ids, known_values)
            
            grounding_pass = validation["is_grounded"]
            has_content = len(report) > 200
            has_sections = "## " in report or "### " in report
            
            s4_checks = [
                (has_content, "Report has substantial content"),
                (has_sections, "Report has markdown sections"),
                (grounding_pass, "Report is grounded (no hallucinated references)"),
            ]
            passed_s4 = sum(1 for ok, _ in s4_checks if ok)
            for ok, label in s4_checks:
                print(f"  {'✅' if ok else '❌'} {label}")
        except Exception as e:
            print(f"  💥 Report generation failed: {e}")
            passed_s4 = 0
            s4_checks = [("", "", "")]
    results["suites"]["report"] = {"passed": passed_s4, "total": len(s4_checks)}

    # === Summary ===
    total = sum(s["total"] for s in results["suites"].values())
    passed = sum(s["passed"] for s in results["suites"].values())
    
    print(f"\n{'='*60}")
    print(f"OVERALL: {passed}/{total} passed ({100*passed/total:.0f}%)")
    print(f"{'='*60}")
    
    import os
    os.makedirs("evals", exist_ok=True)
    with open("evals/eval_results.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    asyncio.run(run_evals())
