import json
from fastapi import Request, HTTPException
from services.v0.user import EmployeeService


async def get_current_email(request: Request) -> str:
    """
    Returns the requester's email address (smtp) as the source-of-truth identity.
    """
    resp = await EmployeeService.get(request=request)

    # EmployeeService.get returns an ORJSONResponse in your current setup
    try:
        payload = json.loads(resp.body.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unable to parse current user payload: {e}")

    email = payload.get("smtp")
    if not email:
        raise HTTPException(status_code=401, detail="Missing smtp/email in current user identity payload.")

    return email.lower()