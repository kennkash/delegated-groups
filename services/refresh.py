# delGroups_mem_refresh/refresh.py

from __future__ import annotations

import time
import urllib.parse
from typing import Iterable, Tuple, Optional, List, Dict

from sas_auth_wrapper import get_external_api_session
from prettiprint import ConsoleUtils

from .dg_services import sync_all_group_owners
from .tokens import AtlassianToken

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
    """
    token = AtlassianToken(app).getCreds()
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# One-time per run: Confluence email map via ScriptRunner
# ---------------------------------------------------------------------------

def fetch_all_confluence_emails() -> Dict[str, Optional[str]]:
    """
    Fetch all active Confluence users and emails using:
      /rest/scriptrunner/latest/custom/getAllEmails

    Returns:
      dict[lower_username -> email]
    """
    headers = _get_auth_header("confluence")
    session = get_external_api_session()

    url = f"{CONF_BASE_URL}scriptrunner/latest/custom/getAllEmails"
    cu.header("Fetching Confluence email map (getAllEmails)")

    resp = session.get(url, headers=headers)
    time.sleep(REQUEST_SLEEP_SECONDS)

    if resp.status_code != 200:
        cu.error(
            f"[Confluence] Failed to fetch getAllEmails "
            f"(status={resp.status_code}): {resp.text[:200]}"
        )
        return {}

    data = resp.json() or []

    email_map: Dict[str, Optional[str]] = {}
    for entry in data:
        lower_username = entry.get("lower_username")
        email = entry.get("email")
        if not lower_username:
            continue
        email_map[lower_username.lower()] = email

    cu.event(f"Loaded {len(email_map)} email entries from getAllEmails", level="SUCCESS")
    return email_map


# ---------------------------------------------------------------------------
# Jira group members via REST API
# ---------------------------------------------------------------------------

def _fetch_jira_group_members(group: str) -> List[Tuple[str, Optional[str]]]:
    """
    Fetch Jira group members via:
      GET /rest/api/2/group/member?groupname=<group>&includeInactiveUsers=false

    Returns:
      list of (username, email) tuples

    Jira response:
      - name = username
      - emailAddress = email
    """
    headers = _get_auth_header("jira")
    session = get_external_api_session()

    encoded_group = urllib.parse.quote(group, safe="")
    api_path = (
        f"{JIRA_BASE_URL}api/2/group/member"
        f"?groupname={encoded_group}&includeInactiveUsers=false"
    )

    members: List[Tuple[str, Optional[str]]] = []
    limit = 50
    start_at = 0

    cu.header(f"Fetching Jira members for group: {group}")

    while True:
        url = f"{api_path}&maxResults={limit}&startAt={start_at}"
        resp = session.get(url, headers=headers)
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
            username = user.get("name")
            email = user.get("emailAddress")
            if username:
                members.append((username, email))

        if data.get("isLast", True):
            cu.event(
                f"Finished Jira member fetch for '{group}'. Found {len(members)} members.",
                level="SUCCESS",
            )
            break

        start_at += limit

    return members


# ---------------------------------------------------------------------------
# Confluence group members via REST API + email_map lookup
# ---------------------------------------------------------------------------

def _fetch_confluence_group_members(
    group: str,
    email_map: Dict[str, Optional[str]],
) -> List[Tuple[str, Optional[str]]]:
    """
    Fetch Confluence group members via:
      GET /rest/api/group/{group}/member?limit=<limit>&start=<start>

    Then enrich email via email_map from getAllEmails.

    Returns:
      list of (username, email) tuples
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
            email = email_map.get(username.lower())
            members.append((username, email))

        if len(results) < limit:
            cu.event(
                f"Finished Confluence member fetch for '{group}'. Found {len(members)} members.",
                level="SUCCESS",
            )
            break

        start += limit

    return members


# ---------------------------------------------------------------------------
# Adapter for dg_services.sync_all_group_owners
# ---------------------------------------------------------------------------

def fetch_members_for_group(
    app: str,
    owning_group_name: str,
    confluence_email_map: Dict[str, Optional[str]],
) -> Iterable[Tuple[str, Optional[str]]]:
    """
    Adapter function used by sync_all_group_owners().

    Given:
      app: 'jira' or 'confluence'
      owning_group_name: group to fetch members for

    Returns:
      iterable of (username, email)
    """
    app = app.lower()

    cu.header("Fetching members for")
    cu.dictionary({"app": app, "group": owning_group_name}, expand=False)

    if app == "jira":
        return _fetch_jira_group_members(owning_group_name)

    if app == "confluence":
        return _fetch_confluence_group_members(owning_group_name, confluence_email_map)

    cu.warning(f"[WARN] Unknown app '{app}' in fetch_members_for_group; returning empty list.")
    return []


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------

def main():
    """
    Scheduled job entrypoint.

    - Fetch Confluence email map once per run.
    - For every configured owning-group relationship in the DB:
      - Fetch members from Jira/Confluence REST APIs
      - Reconcile membership-expanded GROUP_OWNER rows
    """
    cu.header("Starting refresh job")

    # Fetch the Confluence email map once (per run)
    confluence_email_map = fetch_all_confluence_emails()

    def wrapped_fetch(app: str, owning_group_name: str):
        return fetch_members_for_group(app, owning_group_name, confluence_email_map)

    sync_all_group_owners(wrapped_fetch)

    cu.event("Completed refresh job", level="SUCCESS")


if __name__ == "__main__":
    main()