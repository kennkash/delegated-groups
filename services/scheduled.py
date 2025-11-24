# delegated-groups/jobs/run_group_owner_sync.py

from __future__ import annotations

import time
import urllib.parse
from typing import Iterable, Tuple, Optional, List

import requests

from ..services.dg_service import sync_all_group_owners
from ..services.credentials.tokens import AtlassianToken


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# These should be your Jira + Confluence base URLs *ending with* `/rest/`
# so that `base_url + "api/..."` matches your examples.
JIRA_BASE_URL = "https://jira.samsungaustin.com/rest/"
CONF_BASE_URL = "https://confluence.samsungaustin.com/rest/"

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
    session = requests.Session()

    encoded_group = urllib.parse.quote(group, safe="")
    # base path without pagination params
    api_path = (
        f"{JIRA_BASE_URL}api/2/group/member"
        f"?groupname={encoded_group}&includeInactiveUsers=false"
    )

    members: List[Tuple[str, Optional[str]]] = []

    limit = 50
    start_at = 0

    while True:
        url = f"{api_path}&maxResults={limit}&startAt={start_at}"
        resp = session.get(url, headers=headers)

        # respect rate limit: 1 req/sec
        time.sleep(REQUEST_SLEEP_SECONDS)

        if resp.status_code != 200:
            print(
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
    session = requests.Session()

    encoded_group = urllib.parse.quote(group, safe="")
    api_path = f"{CONF_BASE_URL}api/group/{encoded_group}/member"

    members: List[Tuple[str, Optional[str]]] = []

    limit = 200
    start = 0

    while True:
        url = f"{api_path}?limit={limit}&start={start}"
        resp = session.get(url, headers=headers)

        # respect rate limit: 1 req/sec
        time.sleep(REQUEST_SLEEP_SECONDS)

        if resp.status_code != 200:
            print(
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

    if app == "jira":
        return _fetch_jira_group_members(owning_group_name)
    elif app == "confluence":
        return _fetch_confluence_group_members(owning_group_name)
    else:
        print(f"[WARN] Unknown app '{app}' in fetch_members_for_group; returning empty list.")
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
    sync_all_group_owners(fetch_members_for_group)


if __name__ == "__main__":
    main()












/rest/scriptrunner/latest/custom/getUserDetails?username=kkashmiry0641


{
  "displayName": "Kennedy Kashmiry",
  "username": "kkashmiry0641",
  "email": "k.kashmiry@samsung.com",
  "knoxID": "k.kashmiry",
  "imLink": "mysingleim://k.kashmiry",
  "profilePicture": "https://confluence.samsungaustin.com/rest/scriptrunner/latest/custom/getUserAvatar?profilePictureID=96107252",
  "lastLogin": "2025-11-24T18:28:50+0000",
  "memberOf": [
    "automation engineering guest",
    "bc_gotomeeting",
    "BC_youtube",
    "Canon East Users",
    "confluence-administrators",
    "confluence-license-group",
  ],
  "recentPages": [
    {
      "title": "Power User Meeting - 11/5/2025",
      "pageUrl": "/pages/viewpage.action?pageId=775135849",
      "status": "current",
      "id": "775135849",
      "excerpt": " \n\n\nGlobalAD\n\nBackground on Upcoming Changes\n\nCurrent State\n\nPotential Future State\n\nAvailable Alternatives\n\nOpen Discussion\n\n\n\n\n\n\nGlobal AD will be coming to Spotfire by EOY\n\nWe have configured it successfully in our development environment\n\nNeed to conduct a few tests before pushing to production\n\n\n\n\n\n\n\n\nSpotfire is",
      "friendlyLastModified": "Nov 21, 2025",
      "spaceUrl": "/display/SPOTFIRE",
      "spaceTitle": "Spotfire"
    },
    {
      "title": "Announcement Banners with Dismiss Option",
      "pageUrl": "/display/ADMIN/Announcement+Banners+with+Dismiss+Option",
      "status": "current",
      "id": "792702954",
      "excerpt": "Announcement Banner with Dismiss Option - Confluence\n\nScript displays the announcement banner and also a dismiss button that expands into a drop down with options for the dismiss duration (1 hour, 8hrs, indefinitely). The banner is then dismissed/hidden for the duration that the user selected. \n\nThe script also hides t",
      "friendlyLastModified": "Nov 20, 2025",
      "spaceUrl": "/display/ADMIN",
      "spaceTitle": "Knowledge Solutions"
    },
  ],
  "adminSpaces": [
    {
      "name": "14nm Planar Development",
      "key": "14MV",
      "url": "https://confluence.samsungaustin.com/display/14MV",
      "type": "Global"
    },
    {
      "name": "AMHS Engineering",
      "key": "AE",
      "url": "https://confluence.samsungaustin.com/display/AE",
      "type": "Global"
    },
  ]
}

# ---------------------------------------------------------------------------
# Confluence group members via REST API (with ScriptRunner email lookup)
# ---------------------------------------------------------------------------

def _fetch_confluence_group_members(group: str) -> List[Tuple[str, Optional[str]]]:
    """
    Fetch Confluence group members via:
      GET /rest/api/group/{group}/member?limit=<limit>&start=<start>

    For each username, also call ScriptRunner:
      GET /rest/scriptrunner/latest/custom/getUserDetails?username={username}

    Returns:
        list of (username, email) tuples

    This ensures we always have an email for Confluence users (when available),
    so we don't end up creating separate dg_user rows for the same username
    with and without email.
    """
    headers = _get_auth_header("confluence")
    session = get_external_api_session()

    encoded_group = urllib.parse.quote(group, safe="")
    api_path = f"{CONF_BASE_URL}api/group/{encoded_group}/member"

    members: List[Tuple[str, Optional[str]]] = []

    # cache ScriptRunner lookups per run to avoid hitting the endpoint
    # multiple times for the same username
    user_detail_cache: dict[str, Optional[str]] = {}

    def _get_email_for_username(username: str) -> Optional[str]:
        """
        Use ScriptRunner custom REST endpoint to fetch user details, including email.
        """
        if username in user_detail_cache:
            return user_detail_cache[username]

        encoded_username = urllib.parse.quote(username, safe="")
        user_url = (
            f"{CONF_BASE_URL}scriptrunner/latest/custom/getUserDetails"
            f"?username={encoded_username}"
        )

        resp = session.get(user_url, headers=headers)
        time.sleep(REQUEST_SLEEP_SECONDS)  # respect rate limit

        if resp.status_code != 200:
            cu.warning(
                f"[Confluence] Failed to fetch user details for '{username}' "
                f"(status={resp.status_code}): {resp.text[:200]}"
            )
            email = None
        else:
            data = resp.json()
            email = data.get("email")

        user_detail_cache[username] = email
        return email

    limit = 200
    start = 0

    cu.header(f"Starting Confluence group members fetch for group: {group}")
    while True:
        url = f"{api_path}?limit={limit}&start={start}"
        resp = session.get(url, headers=headers)
        time.sleep(REQUEST_SLEEP_SECONDS)  # respect rate limit

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

            # now we enrich with email via ScriptRunner
            email = _get_email_for_username(username)
            members.append((username, email))

        size = len(results)
        if size < limit:
            cu.event(
                f" Finished Confluence group members fetch for group: {group}. "
                f"Found {len(members)} members.",
                level="SUCCESS",
            )
            break

        start += limit

    return members

