#!/usr/bin/env python3
"""Test if we can make FastAPI accept both JSON and FormData."""


from fastapi import FastAPI, File, Form, UploadFile
from pydantic import BaseModel

app = FastAPI()


class AccountData(BaseModel):
    account_name: str
    organization_id: str
    industry: str
    status: str
    websites: list[str]
    timezone: str


@app.post("/test-json")
async def test_json(data: AccountData):
    return {"type": "json", "data": data.dict()}


@app.post("/test-form")
async def test_form(
    account_name: str = Form(...),
    organization_id: str = Form(...),
    industry: str = Form(...),
    status: str = Form(...),
    websites: str = Form(...),
    timezone: str = Form(...),
    files: list[UploadFile] | None = File(None),
):
    return {"type": "form", "account_name": account_name}


# This won't work - FastAPI doesn't allow mixing Body and Form
# @app.post("/test-both")
# async def test_both(
#     data: Union[AccountData, None] = Body(None),
#     account_name: Optional[str] = Form(None)
# ):
#     if data:
#         return {"type": "json", "data": data.dict()}
#     else:
#         return {"type": "form", "account_name": account_name}

if __name__ == "__main__":
    print("Testing endpoint types...")
    print("FastAPI doesn't allow mixing JSON body and Form in the same endpoint")
    print("Solution: Create separate endpoints or force frontend to use FormData")
