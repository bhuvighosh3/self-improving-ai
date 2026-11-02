"""Paired A-side validation runner with real trace-derived scores.

This is a local engineering gate. Repeats are not independent hidden tasks, and a
positive mean is not a significance test. Live and scripted runs are never mixed.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from self_improving_ai.agents.portfolio.service import run_portfolio_agent, save_run
from self_improving_ai.evaluation.portfolio_scoring import score_run
from self_improving_ai.harness.strategies.portfolio_lessons import LessonStore


def benchmark_prompt(case: dict, seed: int) -> tuple[str, dict]:
    reference=copy.deepcopy(case)
    client_ids=list(dict.fromkeys(step["arguments"]["client_id"] for step in reference["steps"]
                       if "client_id" in step.get("arguments",{})))
    instructions=[case["question"], "Trusted synthetic client context: " + ", ".join(client_ids)]
    for item in reference["steps"]:
        if item["tool"]=="project_financial_goal":
            item["arguments"]["seed"]=seed
            for variant in item.get("argument_variants",[]):
                variant["seed"]=seed
            instructions.append(f"Use projection seed {seed}, with 5000 simulation paths.")
    if case.get("answer_shape")=="results_array":
        instructions.append('Return valid JSON with a "results" array containing the full analysis outputs in client order. No markdown.')
    else:
        instructions.append("Return the full final analysis tool result as valid JSON, including units, source, warnings or error code. No markdown.")
    return "\n".join(instructions),reference


async def assess_candidate(store: LessonStore, candidate: dict, cases: list[dict],
                           output: Path, seeds=(42,43,44,45,46), model_factory=None) -> dict:
    """Run fresh baseline/candidate sessions; freeze prompts, input seeds and data.

    model_factory is exclusively for labeled offline transport tests. In live mode
    Gemini randomness is not controlled by the projection seed.
    """
    if len(set(seeds))!=len(seeds) or not seeds:
        raise ValueError("Use distinct, nonempty projection seeds/repeat IDs.")
    if not cases or len({case["id"] for case in cases})!=len(cases):
        raise ValueError("Cases need distinct IDs.")
    if {case.get("split") for case in cases}!={"validation","regression"}:
        raise ValueError("Supply disjoint validation and regression cases; never held-out tests.")
    if any(case.get("provider_fixture") or any(step["tool"] in
           {"get_market_quote","get_external_price_history"} for step in case["steps"]) for case in cases):
        raise ValueError("This paired runner requires frozen local portfolio data.")
    doc=store.read()
    if candidate not in doc.get("candidates",[]) or candidate["base"]!=doc["active"]:
        raise ValueError("Candidate must be registered against the active baseline.")
    baseline=store.active_text()
    if baseline==candidate["text"]:
        raise ValueError("Candidate does not change the baseline.")
    records=[]
    frozen=None
    for case in cases:
        for seed in seeds:
            prompt,reference=benchmark_prompt(case,seed)
            record={"id":f"{case['id']}@{seed}","split":case["split"],"seed":seed,"runs":{}}
            for label,lessons in (("before",baseline),("after",candidate["text"])):
                model=model_factory(case,seed) if model_factory else None
                run=await run_portfolio_agent(prompt,model=model,lessons=lessons)
                save_run(run,output/"runs")
                signature=(run["model"],run["mode"],run["metadata"]["data_sha256"],
                           run["metadata"]["implementation_sha256"])
                if frozen is None:
                    frozen=signature
                if signature!=frozen:
                    raise ValueError("Model, transport, data or code changed during paired evaluation.")
                # Infrastructure failures do not count as failed financial answers.
                if run["status"]!="success":
                    raise ValueError(f"Execution unavailable: {run.get('result',{}).get('error',{}).get('code','unknown')}. Candidate not adopted.")
                record["runs"][label]={"run_id":run["run_id"],"score":score_run(run,reference),
                                      "model_tokens":run["model_tokens"],"elapsed_seconds":run["elapsed_seconds"]}
            records.append(record)
    by_id={record["id"]:record for record in records}
    output.mkdir(parents=True,exist_ok=True)
    evidence_text=json.dumps({"records":records,"frozen_execution":frozen},indent=2,allow_nan=False)
    evidence_path=output/"paired_evidence.json"
    evidence_path.write_text(evidence_text,encoding="utf-8")
    def evaluator(text,case):
        label="before" if text==baseline else "after"
        return float(by_id[case["id"]]["runs"][label]["score"]["passed"])
    gate=store.assess(candidate,evaluator,
        [{"id":r["id"],"split":r["split"]} for r in records if r["split"]=="validation"],
        [{"id":r["id"],"split":r["split"]} for r in records if r["split"]=="regression"],
        evaluation_evidence={"path":str(evidence_path.resolve()),
            "sha256":hashlib.sha256(evidence_text.encode()).hexdigest(),
            "mode":"adk_scripted_transport_test" if model_factory else "adk_gemini"})
    report={"mode":"adk_scripted_transport_test" if model_factory else "adk_gemini",
            "gate":gate,"records":records,"seeds":list(seeds),
            "suite_sha256":hashlib.sha256(json.dumps(cases,sort_keys=True).encode()).hexdigest(),
            "frozen_execution":frozen,
            "limitation":"Engineering gate only; no significance or held-out generalization claim. Projection seeds do not seed Gemini."}
    output.mkdir(parents=True,exist_ok=True)
    (output/"paired_report.json").write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
    return report

