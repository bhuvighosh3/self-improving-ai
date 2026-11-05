import copy
import json

from self_improving_ai.agents.portfolio.service import execute_task
from self_improving_ai.evaluation.portfolio_scoring import score_run

REFERENCE={"tool":"calculate_allocation_drift","arguments":{"client_id":"CLI-001"},
           "checks":[{"path":["total_market_value"],"value":146750},
                     {"path":["currency"],"value":"USD"},
                     {"path":["source"],"value":"synthetic_portfolio"}]}


def agent_run():
    tool=execute_task("allocation",{"client_id":"CLI-001"})
    result=tool["result"]
    return {"mode":"adk_scripted_transport_test","status":"success",
            "trace":[{"kind":"call","id":"c1","tool":REFERENCE["tool"],"arguments":{"client_id":"CLI-001"}},
                     {"kind":"result","id":"c1","tool":REFERENCE["tool"],"result":result}],
            "response":json.dumps(result)}


def test_final_answer_is_scored_not_only_the_tool():
    run=agent_run()
    assert score_run(run,REFERENCE)["passed"]
    bad=json.loads(run["response"])
    bad["total_market_value"]=14675
    run["response"]=json.dumps(bad)
    score=score_run(run,REFERENCE)
    assert score["outcome_correct"]
    assert not score["final_answer_correct"]
    assert not score["passed"]


def test_wrong_units_or_unstructured_answer_cannot_pass():
    for field,value in [("currency","EUR"),("total_market_value",True),("total_market_value","146750")]:
        run=agent_run()
        answer=json.loads(run["response"])
        answer[field]=value
        run["response"]=json.dumps(answer)
        assert not score_run(run,REFERENCE)["passed"]
    run=agent_run()
    run["response"]="Everything is correct."
    assert not score_run(run,REFERENCE)["passed"]


def test_cannot_pair_a_correct_call_with_another_clients_result():
    run=agent_run()
    run["trace"][1]["id"]="some-other-call"
    assert not score_run(run,REFERENCE)["passed"]
    run=agent_run()
    run["trace"][0]["arguments"]["client_id"]="CLI-002"
    assert not score_run(run,REFERENCE)["passed"]


def test_spurious_calls_and_later_wrong_repeats_fail():
    run=agent_run()
    run["trace"].append({"kind":"call","id":"extra","tool":"get_market_quote","arguments":{"symbol":"AAPL"}})
    assert not score_run(run,REFERENCE)["passed"]
    run=agent_run()
    later=copy.deepcopy(run["trace"])
    for entry in later:
        entry["id"]="c2"
    later[1]["result"]["total_market_value"]=1
    run["trace"]+=later
    assert not score_run(run,{**REFERENCE,"max_calls":2})["passed"]


def test_correct_error_reporting_is_successful_agent_behavior():
    run=execute_task("holdings",{"client_id":"CLI-999"})
    reference={"tool":"get_holdings","arguments":{"client_id":"CLI-999"},
               "path":["error","code"],"value":"CLIENT_NOT_FOUND"}
    assert score_run(run,reference)["passed"]
    run.update(mode="adk_scripted_transport_test",status="success",response=json.dumps(run["result"]))
    assert score_run(run,reference)["passed"]
    run["status"]="error"
    assert not score_run(run,reference)["passed"]


def test_dependent_calls_must_be_in_order():
    run=agent_run()
    reference={**REFERENCE,"steps":[
        {"tool":"get_holdings","arguments":{"client_id":"CLI-001"},"path":["total_market_value"],"value":146750},
        REFERENCE]}
    run["trace"].append(execute_task("holdings",{"client_id":"CLI-001"})["trace"][0])
    assert not score_run(run,reference)["passed"]


def test_independent_comparison_calls_can_reorder_but_client_answers_cannot():
    from pathlib import Path
    suite=json.loads((Path(__file__).parents[2]/"src/self_improving_ai/evaluation/eval_sets/portfolio/development.json").read_text())
    reference=next(case for case in suite["cases"] if case["id"]=="A-007")
    chen=execute_task("allocation",{"client_id":"CLI-003"})
    thompson=execute_task("allocation",{"client_id":"CLI-002"})
    run={"mode":"adk_scripted_transport_test","status":"success",
         "trace":thompson["trace"]+chen["trace"],
         "response":json.dumps({"results":[chen["result"],thompson["result"]]})}
    assert score_run(run,reference)["passed"]
    answer=json.loads(run["response"])
    answer["results"][0]["client_id"]="CLI-002"
    run["response"]=json.dumps(answer)
    assert not score_run(run,reference)["passed"]

