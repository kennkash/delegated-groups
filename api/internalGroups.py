@router.get("/conf-internal-groups",  status_code=200, summary="Get Confluence internal groups", response_model=SimpleList)
async def conf_internal_groups():
    
    """
    conf_internal_groups returns the internal Confluence groups that can be added as owners.

    <details><summary><span>Parameters</span></summary>
    
     * `None`
    </details>

    <details><summary><span>Returns</span></summary>
    
    A list of internal Confluence groups
    </details>
    
    """
    # Initializing API Connection
    conf_client = ConfAPIClient()
    api_path = f'scriptrunner/latest/custom/internalGroups'

    # ----- network / transport errors ---------------------------------
    try:
        resp = await conf_client.get(api_path)
    except Exception as exc:          # e.g., connection timeout, DNS failure …
        error_response(
            f"Network error while pulling internal Confluence groups': {exc}",
            status_code=status.HTTP_502_BAD_GATEWAY,
            title="Network Failure",
        )

    # ----- HTTP‑level errors -----------------------------------------
    if not resp:
        # Try to pull a helpful message from the body
        try:
            err_msg = resp.json().get("message", resp.text)
        except Exception:
            err_msg = resp.text or f"Status {resp.status_code}"
        
        error_response(
        f"Failed to pull internal Confluence groups': {err_msg}",
        status_code=resp.status_code,
        title="Remote Service Error",
        )
    extra_filters = ["SAS ALL"]
    response = filter_items(resp, prefixes=extra_filters) 
    return response


@router.get("/jira-internal-groups",  status_code=200, summary="Get Jira internal groups", response_model=SimpleList)
async def jira_internal_groups():
    
    """
    jira_internal_groups returns the internal Jira groups that can be added as owners.

    <details><summary><span>Parameters</span></summary>
    
     * `None`
    </details>

    <details><summary><span>Returns</span></summary>
    
    A list of internal Jira groups
    </details>
    
    """
    # Initializing API Connection
    jira_client = JiraAPIClient()
    api_path = f'scriptrunner/latest/custom/internalGroups'

    # ----- network / transport errors ---------------------------------
    try:
        resp = await jira_client.get(api_path)
    except Exception as exc:          # e.g., connection timeout, DNS failure …
        error_response(
            f"Network error while pulling internal Jira groups': {exc}",
            status_code=status.HTTP_502_BAD_GATEWAY,
            title="Network Failure",
        )

    # ----- HTTP‑level errors -----------------------------------------
    if not resp:
        # Try to pull a helpful message from the body
        try:
            err_msg = resp.json().get("message", resp.text)
        except Exception:
            err_msg = resp.text or f"Status {resp.status_code}"
        
        error_response(
        f"Failed to pull internal Jira groups': {err_msg}",
        status_code=resp.status_code,
        title="Remote Service Error",
        )
    extra_filters = ["SAS ALL"]
    response = filter_items(resp, prefixes=extra_filters) 
    return response
    
    
    
    
from typing import Optional, List
from fastapi import Query, status

# Keep your existing endpoints unchanged above this line.

@router.get(
    "/conf-internal-groups/search",
    status_code=200,
    summary="Search Confluence internal groups (typeahead)",
    response_model=SimpleList,
)
async def conf_internal_groups_search(
    q: str = Query(..., min_length=2, description="Search term (case-insensitive contains)"),
    limit: int = Query(25, ge=1, le=100, description="Max number of matches to return"),
):
    conf_client = ConfAPIClient()
    api_path = "scriptrunner/latest/custom/internalGroups"

    try:
        resp = await conf_client.get(api_path)
    except Exception as exc:
        error_response(
            f"Network error while searching internal Confluence groups: {exc}",
            status_code=status.HTTP_502_BAD_GATEWAY,
            title="Network Failure",
        )

    if not resp:
        try:
            err_msg = resp.json().get("message", resp.text)
        except Exception:
            err_msg = resp.text or f"Status {resp.status_code}"
        error_response(
            f"Failed to search internal Confluence groups: {err_msg}",
            status_code=resp.status_code,
            title="Remote Service Error",
        )

    extra_filters = ["SAS ALL"]
    groups = filter_items(resp, prefixes=extra_filters)

    # Normalize to list[str]
    names: List[str] = []
    for item in groups:
        if isinstance(item, dict):
            n = item.get("name")
            if n:
                names.append(str(n))
        else:
            names.append(str(item))

    q_lower = q.lower()
    matches = [n for n in names if q_lower in n.lower()]

    return matches[:limit]


@router.get(
    "/jira-internal-groups/search",
    status_code=200,
    summary="Search Jira internal groups (typeahead)",
    response_model=SimpleList,
)
async def jira_internal_groups_search(
    q: str = Query(..., min_length=2, description="Search term (case-insensitive contains)"),
    limit: int = Query(25, ge=1, le=100, description="Max number of matches to return"),
):
    jira_client = JiraAPIClient()
    api_path = "scriptrunner/latest/custom/internalGroups"

    try:
        resp = await jira_client.get(api_path)
    except Exception as exc:
        error_response(
            f"Network error while searching internal Jira groups: {exc}",
            status_code=status.HTTP_502_BAD_GATEWAY,
            title="Network Failure",
        )

    if not resp:
        try:
            err_msg = resp.json().get("message", resp.text)
        except Exception:
            err_msg = resp.text or f"Status {resp.status_code}"
        error_response(
            f"Failed to search internal Jira groups: {err_msg}",
            status_code=resp.status_code,
            title="Remote Service Error",
        )

    extra_filters = ["SAS ALL"]
    groups = filter_items(resp, prefixes=extra_filters)

    # Normalize to list[str]
    names: List[str] = []
    for item in groups:
        if isinstance(item, dict):
            n = item.get("name")
            if n:
                names.append(str(n))
        else:
            names.append(str(item))

    q_lower = q.lower()
    matches = [n for n in names if q_lower in n.lower()]

    return matches[:limit]