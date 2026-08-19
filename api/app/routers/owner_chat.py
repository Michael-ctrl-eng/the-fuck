from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..deps import DbDep, MembershipDep, OrgDep
from ..models import OwnerMessage
from ..services.owner_chat import parse_owner_instruction

router = APIRouter(prefix="/api/agent", tags=["agent"])

class InstructionRequest(BaseModel):
    text: str
    image_url: str = ""

class InstructionResponse(BaseModel):
    ok: bool
    agent_response: str
    action_taken: dict

@router.post("/chat", response_model=InstructionResponse)
async def chat_with_agent(
    body: InstructionRequest, db: DbDep, org: OrgDep, membership: MembershipDep
):
    response_text, action = await parse_owner_instruction(db, org, body.text, body.image_url)
    
    msg = OwnerMessage(
        org_id=org.id,
        user_id=membership.user_id,
        text=body.text,
        image_url=body.image_url,
        parsed_action=action,
        agent_response=response_text
    )
    db.add(msg)
    await db.commit()
    
    return InstructionResponse(ok=True, agent_response=response_text, action_taken=action)
