# api/v0/endpoints/user.py
from fastapi import APIRouter, Request
from fastapi.responses import ORJSONResponse
from services.util.errorResponse import error_response_noarg
from services.v0.user import EmployeeService

router = APIRouter()


@router.get("", status_code=200, summary="Get current user information", responses=error_response_noarg(), tags=["secure"])
async def fetch_user(*, request: Request) -> ORJSONResponse:
    """
    fetch_user get the user information for the individual that made the request

    Args:
        request (Request): fastapi request payload

    Returns ORJSONResponse:
        
        {
            "ghr_id": "12345678",

            "full_name": "John Doe",

            "cost_center_name": "Manufacturing System",

            "title": "Engineer I",

            "mysingle_id": "j.doe",
            
            "nt_id": "jdoe123",

            "user": "j.doe"
        }
    """
    result = await EmployeeService.get(request=request)
    return result



current_user = await fetch_user(request=request)
    admin_user = current_user.body
    admin_user_str = admin_user.decode('utf-8')
    
    # Parse the JSON string to a dictionary
    admin_user_json = json.loads(admin_user_str)
    
    # Extract the value of "nt_id"
    nt_id = admin_user_json.get("nt_id", "default_nt_id")
