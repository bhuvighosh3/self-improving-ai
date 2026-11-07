"""Email CRUD endpoints backed by Cloud Firestore."""

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from self_improving_ai.email_store import EmailStore

router = APIRouter(prefix="/api/email", tags=["email"])
_store = EmailStore()

_CATEGORIES = Literal["client", "internal", "compliance", "market_update", "scheduling"]
_FOLDERS = Literal["inbox", "sent", "drafts", "archive"]


class EmailCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    subject: str = Field(min_length=1, max_length=300)
    to_name: str = Field(min_length=1, max_length=100)
    to_addr: str = Field(min_length=1, max_length=200)
    client_id: str = Field(default="", max_length=30)
    category: _CATEGORIES = "client"
    body: str = Field(min_length=1, max_length=10000)
    folder: _FOLDERS = "sent"


class EmailUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    read: bool | None = None
    starred: bool | None = None
    folder: _FOLDERS | None = None


@router.get("/messages")
async def list_emails(folder: str = "inbox"):
    return await run_in_threadpool(_store.list_emails, folder)


@router.get("/messages/{email_id}")
async def get_email(email_id: str):
    try:
        return await run_in_threadpool(_store.get_email, email_id)
    except LookupError:
        raise HTTPException(404, "Email not found")


@router.post("/messages", status_code=201)
async def create_email(body: EmailCreate):
    return await run_in_threadpool(_store.create_email, body.model_dump())


@router.patch("/messages/{email_id}")
async def update_email(email_id: str, body: EmailUpdate):
    try:
        return await run_in_threadpool(
            _store.update_email, email_id, body.model_dump(exclude_none=True)
        )
    except LookupError:
        raise HTTPException(404, "Email not found")


@router.delete("/messages/{email_id}", status_code=204)
async def delete_email(email_id: str):
    try:
        await run_in_threadpool(_store.delete_email, email_id)
    except LookupError:
        raise HTTPException(404, "Email not found")
