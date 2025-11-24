def fetch_all_confluence_emails() -> dict[str, Optional[str]]:
    """
    Fetch all Confluence users and their emails from ScriptRunner getAllEmails.
    Returns:
        dict[lower_username -> email]
    """
    headers = _get_auth_header("confluence")
    session = get_external_api_session()

    url = f"{CONF_BASE_URL}scriptrunner/latest/custom/getAllEmails"
    cu.header("Fetching Confluence user email map via getAllEmails")

    resp = session.get(url, headers=headers)
    time.sleep(REQUEST_SLEEP_SECONDS)  # respect rate limit

    if resp.status_code != 200:
        cu.error(
            f"[Confluence] Failed to fetch getAllEmails "
            f"(status={resp.status_code}): {resp.text[:200]}"
        )
        return {}

    data = resp.json() or []

    email_map = {
        entry["lower_username"].lower(): entry.get("email")
        for entry in data
        if entry.get("lower_username")
    }

    cu.event(f"Loaded {len(email_map)} email entries from getAllEmails", level="INFO")
    return email_map
    
    
    def _fetch_confluence_group_members(group: str, email_map: dict[str, Optional[str]]) -> List[Tuple[str, Optional[str]]]:
    """
    Fetch Confluence group members via /api/group/.../member
    Use email_map (preloaded from getAllEmails) to enrich email.
    """
    headers = _get_auth_header("confluence")
    session = get_external_api_session()

    encoded_group = urllib.parse.quote(group, safe="")
    api_path = f"{CONF_BASE_URL}api/group/{encoded_group}/member"

    members: List[Tuple[str, Optional[str]]] = []

    limit = 200
    start = 0

    cu.header(f"Fetching Confluence members for group: {group}")

    while True:
        url = f"{api_path}?limit={limit}&start={start}"
        resp = session.get(url, headers=headers)
        time.sleep(REQUEST_SLEEP_SECONDS)

        if resp.status_code != 200:
            cu.error(
                f"[Confluence] Failed to fetch members for group '{group}' "
                f"(status={resp.status_code}): {resp.text[:200]}"
            )
            break

        data = resp.json()
        results = data.get("results", []) or []

        for user in results:
            username = user.get("username")
            if not username:
                continue

            lower_username = username.lower()
            email = email_map.get(lower_username)
            members.append((username, email))

        if len(results) < limit:
            cu.event(
                f" Finished Confluence member fetch for '{group}'. "
                f"Found {len(members)} members.",
                level="SUCCESS",
            )
            break

        start += limit

    return members
    
    
    def fetch_members_for_group(app: str, owning_group_name: str, email_map: dict[str, Optional[str]]):
    """
    Adapter used by dg_service.sync_all_group_owners.
    """
    app = app.lower()

    if app == "jira":
        return _fetch_jira_group_members(owning_group_name)

    elif app == "confluence":
        return _fetch_confluence_group_members(owning_group_name, email_map)

    else:
        cu.warning(f"[WARN] Unknown app '{app}' in fetch_members_for_group")
        return []
        
        
        def main():
    cu.header("Starting main refresh job")

    # Load confluence email map ONCE
    email_map = fetch_all_confluence_emails()

    # Pass a wrapper closure to sync_all_group_owners
    def wrapped_fetch(app: str, owning_group_name: str):
        return fetch_members_for_group(app, owning_group_name, email_map)

    sync_all_group_owners(wrapped_fetch)

    cu.event("Completed main refresh job", level="SUCCESS")