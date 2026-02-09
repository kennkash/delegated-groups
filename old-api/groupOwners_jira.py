import urllib.parse
from typing import Any, Dict
from fastapi_cache.decorator import cache

from services.external_api.jiraRequests import JiraAPIClient
from services.userprofilespic import ProfilePicFetcher  # adjust import path

jira_client = JiraAPIClient()

@cache(expire=60 * 30, namespace="jira_user")  # 30 minutes
async def _fetch_jira_user_cached(username: str) -> Dict[str, Any]:
    """
    ONE Jira call total (cached):
      /rest/api/2/user?username=<username>

    Returns the frontend-shaped owner object:
      { username, userKey, displayName, profilePictureId, avatarId, ownerId }
    """
    enc = urllib.parse.quote(username, safe="")
    try:
        user_payload = await jira_client.get(f"api/2/user?username={enc}")
    except Exception:
        parts = ProfilePicFetcher.jira_avatar_parts_from_profile_picture_id("avatarId=10122")
        return {
            "username": username,
            "userKey": username,
            "displayName": "Inactive User [X]",
            "profilePictureId": parts["profilePictureId"],
            "avatarId": parts["avatarId"],
            "ownerId": parts["ownerId"],
        }

    # profilePictureId query-string per your rules (no extra call)
    prof_id = ProfilePicFetcher.normalize_jira_profile_picture_id(user_payload)
    parts = ProfilePicFetcher.jira_avatar_parts_from_profile_picture_id(prof_id)

    active = user_payload.get("active") is True
    display = user_payload.get("displayName") if active else "Inactive User [X]"

    return {
        "username": username,
        "userKey": user_payload.get("key") or username,
        "displayName": display,
        "profilePictureId": parts["profilePictureId"],
        "avatarId": parts["avatarId"],
        "ownerId": parts["ownerId"],
    }
    
    
#member
# inside your existing get_members() loop over response_json["values"]:
profile_picture_id_qs = ProfilePicFetcher.normalize_jira_profile_picture_id(result)
parts = ProfilePicFetcher.jira_avatar_parts_from_profile_picture_id(profile_picture_id_qs)

member_names.append({
    "username": result["name"],
    "userKey": result["key"],
    "displayName": result["displayName"],
    "profilePictureId": parts["profilePictureId"],
    "avatarId": parts["avatarId"],
    "ownerId": parts["ownerId"],
})

import asyncio
import json
from typing import Any, Dict, List

from fastapi import Depends, Path
from fastapi.responses import ORJSONResponse
from sqlalchemy.orm import Session

from db import get_db
from models import DgManagedGroup, DgUser, DgGroupOwner, DgGroupOwnerGroup  # adjust imports

def _dedupe_by_username(users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    dedup: Dict[str, Dict[str, Any]] = {}
    for u in users:
        uname = u.get("username")
        if uname and uname not in dedup:
            dedup[uname] = u
    return list(dedup.values())

@router.get(
    "/groupowners/{group}",
    status_code=200,
    summary="Get all group owners",
    response_model=GroupOwnerResponse,
)
async def get_owners(
    group: str = Path(..., example="digital_solutions"),
    db: Session = Depends(get_db),
) -> ORJSONResponse:
    managed_group = (
        db.query(DgManagedGroup)
        .filter(DgManagedGroup.app == "jira")
        .filter(DgManagedGroup.lower_group_name == group.lower())
        .one_or_none()
    )

    if not managed_group:
        return ORJSONResponse(
            content={
                "message": "Not a delegated group",
                "allUserOwners": [],
                "group": group,
                "groupOwners": "",
                "userOwners": [],
            },
            status_code=200,
        )

    canonical_group_name = managed_group.group_name

    # Direct USER_OWNER → usernames
    user_owner_rows = (
        db.query(DgUser.username)
        .join(DgGroupOwner, DgGroupOwner.user_id == DgUser.id)
        .filter(DgGroupOwner.managed_group_id == managed_group.id)
        .filter(DgGroupOwner.source_type == "USER_OWNER")
        .order_by(DgUser.lower_username)
        .all()
    )
    direct_usernames = [r[0] for r in user_owner_rows]

    # GROUP_OWNER → owning groups
    group_owner_rows = (
        db.query(DgGroupOwnerGroup.owning_group_name)
        .filter(DgGroupOwnerGroup.managed_group_id == managed_group.id)
        .order_by(DgGroupOwnerGroup.lower_owning_group_name)
        .all()
    )
    owning_groups = [r[0] for r in group_owner_rows]

    group_owners_str = ",".join(owning_groups)

    # Build userOwners (cached, 1 Jira call each)
    user_owners: List[Dict[str, Any]] = []
    if direct_usernames:
        user_owners = await asyncio.gather(*[_fetch_jira_user_cached(u) for u in direct_usernames])

    # Expand owning groups → members via your existing get_members()
    inherited_users: List[Dict[str, Any]] = []
    if owning_groups:
        member_responses = await asyncio.gather(*[get_members(group=g) for g in owning_groups])
        for resp in member_responses:
            inherited_users.extend(json.loads(resp.body.decode("utf-8")))

    all_user_owners = _dedupe_by_username(inherited_users + user_owners)

    return ORJSONResponse(
        content={
            "userOwners": user_owners,
            "groupOwners": group_owners_str,
            "allUserOwners": all_user_owners,
            "group": canonical_group_name,
        },
        status_code=200,
    )
