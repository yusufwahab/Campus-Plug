from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field

from app.deps import DB
from app.models.system import ContactMessage
from app.ratelimit import rate_limit

router = APIRouter(tags=["support"])


class ContactIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    topic: Literal["order", "payment", "account", "report", "other"]
    message: str = Field(min_length=10, max_length=3000)


@router.post("/contact", status_code=201, dependencies=[Depends(rate_limit("contact", 5, 3600))])
def contact(body: ContactIn, db: DB) -> dict[str, str]:
    db.add(ContactMessage(name=body.name, email=body.email.lower(), topic=body.topic, message=body.message))
    db.commit()
    return {"status": "received"}
