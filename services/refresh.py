# delegated-groups/jobs/run_group_owner_sync.py

from __future__ import annotations

import time
import urllib.parse
from typing import Iterable, Tuple, Optional, List

from sas_auth_wrapper import get_external_api_session

from .dg_services import sync_all_group_owners
from .tokens import AtlassianToken

from prettiprint import ConsoleUtils

cu = ConsoleUtils(theme="dark", verbosity=2)
# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# These should be your Jira + Confluence base URLs *ending with* `/rest/`
# so that `base_url + "api/..."` matches your examples.
JIRA_BASE_URL = "http://jira.externalapi.smartcloud.samsungaustin.com/rest/"
CONF_BASE_URL = "http://confluence.externalapi.smartcloud.samsungaustin.com/rest/"

# Rate limiting: 1 request/sec, 60/min
REQUEST_SLEEP_SECONDS = 1.05


def _get_auth_header(app: str) -> dict:
    """
    Get Authorization header for the given app using your existing token helper.

    Assumes:
    AtlassianToken(app).getCreds() -> returns a bearer token/password.

    If you instead have an async getCreds(app), you could adapt this script
    to be async and use asyncio.run(...) at the bottom.
    """
    token = AtlassianToken(app).getCreds()
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Jira group members via REST API
# ---------------------------------------------------------------------------

def _fetch_jira_group_members(group: str) -> List[Tuple[str, Optional[str]]]:
    """
    Fetch Jira group members via:
    GET /rest/api/2/group/member?groupname=<group>&includeInactiveUsers=false

    Returns:
    list of (username, email) tuples

    In Jira's response:
    - name = username
    - emailAddress = email (may be null/omitted)
    """
    headers = _get_auth_header("jira")
    session = get_external_api_session()

    encoded_group = urllib.parse.quote(group, safe="")
    # base path without pagination params
    api_path = (
        f"{JIRA_BASE_URL}api/2/group/member"
        f"?groupname={encoded_group}&includeInactiveUsers=false"
    )

    members: List[Tuple[str, Optional[str]]] = []

    limit = 50
    start_at = 0

    cu.header(f"Starting Jira group members fetch for group: {group}")
    while True:
        url = f"{api_path}&maxResults={limit}&startAt={start_at}"
        resp = session.get(url, headers=headers)

        # respect rate limit: 1 req/sec
        time.sleep(REQUEST_SLEEP_SECONDS)

        if resp.status_code != 200:
            cu.error(
                f"[Jira] Failed to fetch members for group '{group}' "
                f"(status={resp.status_code}): {resp.text[:200]}"
            )
            break

        data = resp.json()
        values = data.get("values", []) or []

        for user in values:
            username = user.get("name")  # Jira DC username
            email = user.get("emailAddress")
            if username:
                members.append((username, email))

        # Pagination: use isLast to decide if done
        is_last = data.get("isLast", True)
        if is_last:
            cu.event(f" Finished Jira group members fetch for group: {group}. Found {len(members)} members.", level="SUCCESS")
            break

        # Otherwise, advance
        start_at += limit

    return members


# ---------------------------------------------------------------------------
# Confluence group members via REST API
# ---------------------------------------------------------------------------

def _fetch_confluence_group_members(group: str) -> List[Tuple[str, Optional[str]]]:
    """
    Fetch Confluence group members via:
    GET /rest/api/group/{group}/member?limit=<limit>&start=<start>

    Returns:
    list of (username, email) tuples

    In your example response:
    - username = Confluence username
    - email is NOT present in this payload, so we set email=None
        (your dg_user model allows email to be nullable).
    """
    headers = _get_auth_header("confluence")
    session = get_external_api_session()

    encoded_group = urllib.parse.quote(group, safe="")
    api_path = f"{CONF_BASE_URL}api/group/{encoded_group}/member"

    members: List[Tuple[str, Optional[str]]] = []

    limit = 200
    start = 0

    cu.header(f"Starting Confluence group members fetch for group: {group}")
    while True:
        url = f"{api_path}?limit={limit}&start={start}"
        resp = session.get(url, headers=headers)

        # respect rate limit: 1 req/sec
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
            # Confluence REST here doesn't expose email -> store None
            email = None
            if username:
                members.append((username, email))

        size = len(results)
        if size < limit:
            # No more pages
            cu.event(f" Finished Confluence group members fetch for group: {group}. Found {len(members)} members.", level="SUCCESS")
            break

        start += limit

    return members


# ---------------------------------------------------------------------------
# Adapter used by dg_service.sync_all_group_owners
# ---------------------------------------------------------------------------

def fetch_members_for_group(
    app: str,
    owning_group_name: str,
) -> Iterable[Tuple[str, Optional[str]]]:
    """
    Adapter function passed into sync_all_group_owners().

    Given:
    app: 'jira' or 'confluence'
    owning_group_name: value stored in via_group_name

    Returns:
    iterable of (username, email) for current members of that group.

    This function chooses the correct REST API based on app.
    """
    app = app.lower()
    dict = {"app": f"{app}", "group": f"{owning_group_name}"}
    cu.header("Fetching members for:")
    cu.dictionary(dict, expand=False)
    if app == "jira":
        return _fetch_jira_group_members(owning_group_name)
    elif app == "confluence":
        return _fetch_confluence_group_members(owning_group_name)
    else:
        cu.warning(f"[WARN] Unknown app '{app}' in fetch_members_for_group; returning empty list.")
        return []

# ---------------------------------------------------------------------------
# Main entrypoint for scheduler
# ---------------------------------------------------------------------------

def main():
    """
    Scheduled job entrypoint.

    - Finds all (app, delegated_group, via_group_name) with GROUP_OWNER rows.
    - For each, calls the appropriate REST API to get CURRENT group membership.
    - Reconciles dg_group_owner rows using sync_group_owners_for_delegated_group().
    """
    cu.header("Starting main refresh job")
    sync_all_group_owners(fetch_members_for_group)
    cu.event("Completed main refresh job", level="SUCCESS")

if __name__ == "__main__":
    main()
