"""Component A endpoints; explicit calculations and model-driven requests are separate."""
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.concurrency import run_in_threadpool

from self_improving_ai.agents.portfolio.service import execute_task, run_portfolio_agent

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class CalculationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    task: Literal["holdings", "scenarios", "allocation", "risk", "projection", "quote", "history"]
    client_id: str = Field(default="CLI-001", max_length=30)
    account_id: str = Field(default="", max_length=50)
    symbol: str = Field(default="AAPL", max_length=20)
    start_date: str = ""
    end_date: str = ""
    num_simulations: int = Field(default=5000, ge=1, le=100000)
    seed: int = Field(default=42, ge=0, le=4294967295)
    target_stock_weight: float | None = Field(default=None, ge=0, le=1)
    target_amount: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    years: int | None = Field(default=None, ge=1, le=120)
    annual_contribution: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    annual_withdrawal: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def reject_ignored_scenarios(self):
        if self.task != "allocation" and self.target_stock_weight is not None:
            raise ValueError("Stock target is only supported for allocation drift.")
        if self.task != "projection" and any(getattr(self, key) is not None for key in
                ("target_amount", "years", "annual_contribution", "annual_withdrawal")):
            raise ValueError("Goal overrides are only supported for goal projection.")
        if self.account_id and self.task not in {"holdings", "allocation", "risk"}:
            raise ValueError("This task does not support an account filter.")
        return self


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=3000)


@router.post("/execute")
async def calculate(request: CalculationRequest):
    args = {"client_id": request.client_id}
    if request.task in {"holdings", "allocation", "risk"}:
        args["account_id"] = request.account_id
    if request.task == "projection":
        args.update(num_simulations=request.num_simulations, seed=request.seed)
        args.update({key: getattr(request, key) for key in
                     ("target_amount", "years", "annual_contribution", "annual_withdrawal")
                     if getattr(request, key) is not None})
    if request.task == "allocation" and request.target_stock_weight is not None:
        args["target_stock_weight"] = request.target_stock_weight
    if request.task in {"quote", "history"}:
        args = {"symbol": request.symbol}
    if request.task == "history":
        args.update(start_date=request.start_date, end_date=request.end_date)
    return await run_in_threadpool(execute_task, request.task, args)


@router.post("/agent")
async def ask_agent(request: AgentRequest):
    return await run_portfolio_agent(request.message)
