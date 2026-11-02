import json

import pytest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from self_improving_ai.agents.portfolio.answer_validation import unsupported_currency_amounts
from self_improving_ai.agents.portfolio.service import execute_task, run_portfolio_agent
from tests.test_agents.test_portfolio_agent import ScriptedModel


def trace_for(task="allocation"):
    run=execute_task(task,{"client_id":"CLI-001"})
    return [{"kind":"result","result":run["result"]}]


def test_unfounded_dollar_equivalent_of_drift_is_rejected():
    text="Drift: +19.86 percentage points ($19,863.71, weight difference). Adjustment: -$29,150.00."
    assert unsupported_currency_amounts(text,trace_for())==[19863.71]


@pytest.mark.parametrize("text",[
    "Total $146,750.00; reduce stocks by $29,150 and add USD 29,150 to bonds.",
    "Total USD 146750, or $146.8K. Stock value: 117200 USD. Drift: 19.86 pp.",
    "The portfolio is about $0.15 million.",
])
def test_tool_values_rounding_and_units_are_not_false_positives(text):
    assert unsupported_currency_amounts(text,trace_for())==[]


def test_account_subtotals_are_supported_but_invented_totals_are_not():
    assert unsupported_currency_amounts("Accounts: $104,300 and $42,450.",trace_for("holdings"))==[]
    assert unsupported_currency_amounts("Total $200,000",trace_for("holdings"))==[200000]
    assert unsupported_currency_amounts("Did you mean a $200,000 goal?",[])==[]


def test_scenario_currency_notes_are_preserved_and_latex_is_not_currency():
    trace=[{"kind":"result","result":{"status":"success","target_amount":120000,
        "assumption":"Based on a $600000 home and the CRM's $4200/month withdrawal."}}]
    assert unsupported_currency_amounts(
        r"Home: $600,000. Monthly: $4,200. Correlation: $0.00108 / (0.18 \times 0.06)$.",trace)==[]
    assert unsupported_currency_amounts(
        "Wrong dollar amount: $19,863.71 (weight difference), and target $120,000.",trace)==[19863.71]


def test_extreme_model_amount_is_rejected_without_nonfinite_error_metadata():
    result=unsupported_currency_amounts("$"+"9"*400,trace_for())
    assert result==["out_of_range_currency_amount"]
    json.dumps(result,allow_nan=False)


class WrongAmountModel(ScriptedModel):
    async def generate_content_async(self,llm_request,stream=False):
        if any(part.function_response for content in llm_request.contents for part in content.parts or []):
            yield LlmResponse(content=types.Content(role="model",parts=[types.Part(text=
                "Drift is 19.86 pp ($19,863.71). Adjust stocks by -$29,150.")]))
        else:
            async for event in super().generate_content_async(llm_request,stream):
                yield event


@pytest.mark.asyncio
async def test_answer_mismatch_retains_real_tools_but_does_not_display_bad_prose():
    run=await run_portfolio_agent("Garcia allocation",model=WrongAmountModel())
    assert run["status"]=="error"
    assert run["result"]["error"]["code"]=="MODEL_ANSWER_MISMATCH"
    assert run["result"]["error"]["retryable"]
    assert run["response"]==""
    assert "29150" in json.dumps(run["trace"])
