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
