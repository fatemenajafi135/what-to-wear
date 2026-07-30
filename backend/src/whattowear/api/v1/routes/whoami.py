"""GET /api/v1/whoami — see specs/003-auth/contracts/whoami.md.

Not a product endpoint. Proves `get_current_user_id` end to end through a
real route, per the feature handoff §5.3.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from whattowear.auth import get_current_user_id

router = APIRouter()


class WhoamiResponse(BaseModel):
    user_id: str


@router.get("/whoami")
def whoami(user_id: str = Depends(get_current_user_id)) -> WhoamiResponse:
    return WhoamiResponse(user_id=user_id)
