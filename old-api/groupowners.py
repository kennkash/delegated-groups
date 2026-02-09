import asyncio
import urllib.parse
from typing import Any, Dict, List, Optional

from fastapi_cache.decorator import cache

from services.profile_pic_fetcher import ProfilePicFetcher
from services.external_api.confRequests import ConfAPIClient

conf_client = ConfAPIClient()


@cache(expire=60 * 30, namespace="conf_user")  # 30 min; tweak if you want
async def _fetch_conf_user_cached(username: str) -> Dict[str, Any]:
    """
    Cached Confluence user lookup returning legacy-shaped object:
      { username, displayName, profilePictureId }

    - displayName from Confluence user API
    - profilePictureId from ProfilePicFetcher.fetchC_profpic() normalization
    """
    # displayName
    try:
        data = await conf_client.get(f"api/user?username={urllib.parse.quote(username)}")
        display = data.get("displayName") or "Inactive User [X]"
    except Exception:
        display = "Inactive User [X]"

    # profilePictureId (trusted normalization)
    try:
        prof_id = await ProfilePicFetcher(username).fetchC_profpic()
    except Exception:
        prof_id = "default"

    return {"username": username, "displayName": display, "profilePictureId": prof_id}
    
    async def _fetch_conf_group_members_all(group_name: str) -> List[Dict[str, Any]]:
    """
    Expand Confluence group -> list of legacy-shaped user objects
    with pagination support.

    Returns list of:
      { username, displayName, profilePictureId }
    """
    enc_group = urllib.parse.quote(group_name, safe="")
    start = 0
    limit = 200  # bump if your instance allows larger
    out: List[Dict[str, Any]] = []

    while True:
        # Confluence group member endpoint you already use:
        # /rest/api/group/{group}/member?start=0&limit=200
        payload = await conf_client.get(f"api/group/{enc_group}/member?start={start}&limit={limit}")
        results = payload.get("results") or []

        # Convert results into your legacy-shaped user objects.
        # Some instances include profilePicture/path here, but we’ll still normalize via fetcher
        # ONLY if you want strict consistency. To avoid N extra calls, we can:
        # - use payload displayName directly
        # - use ProfilePicFetcher only for users missing picture/path
        #
        # Since you want strict consistency, we’ll normalize ALL via fetcher,
        # but do it concurrently.
        usernames: List[str] = []
        display_by_username: Dict[str, str] = {}

        for u in results:
            uname = u.get("username")
            if not uname:
                continue
            usernames.append(uname)
            display_by_username[uname] = u.get("displayName") or "Inactive User [X]"

        # Fetch normalized profilePictureId in parallel, and use cached user object
        # (which also gives displayName, but we prefer the group endpoint displayName when present)
        users = await asyncio.gather(*[_fetch_conf_user_cached(uname) for uname in usernames])

        # Override displayName from group-member payload if it had one
        for user in users:
            uname = user["username"]
            if uname in display_by_username and display_by_username[uname]:
                user["displayName"] = display_by_username[uname]
        out.extend(users)

        # ---- pagination detection ----
        # Pattern A: Confluence style paging: start, limit, size
        size = payload.get("size")
        if isinstance(size, int):
            # If we received fewer than limit, likely done
            if len(results) < limit:
                break
            start += limit
            continue

        # Pattern B: _links.next
        links = payload.get("_links") or {}
        next_link = links.get("next")
        if next_link:
            # next_link is usually a relative URL like "/rest/api/...start=200..."
            # We can parse start from it, otherwise just increment.
            parsed = urllib.parse.urlparse(next_link)
            qs = urllib.parse.parse_qs(parsed.query)
            next_start = qs.get("start", [None])[0]
            if next_start is not None:
                try:
                    start = int(next_start)
                    continue
                except ValueError:
                    pass
            start += limit
            continue

        # Pattern C: no paging fields -> assume one page
        break

    return out
    
    
    from fastapi import Depends, HTTPException, Path
from fastapi.responses import ORJSONResponse
from sqlalchemy.orm import Session

from db import get_db
from models import DgManagedGroup, DgUser, DgGroupOwner, DgGroupOwnerGroup  # adjust imports


@router.get(
    "/groupowners/{group}",
    status_code=200,
    summary="Get all group owners",
    response_model=ConfGroupOwnerResponse,
)
async def get_owners(
    group: str = Path(..., example="Cleans"),
    db: Session = Depends(get_db),
) -> ORJSONResponse:
    group_lower = group.lower()

    managed_group = (
        db.query(DgManagedGroup)
        .filter(DgManagedGroup.app == "confluence")
        .filter(DgManagedGroup.lower_group_name == group_lower)
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

    # Direct USER_OWNER users
    user_owner_rows = (
        db.query(DgUser.username)
        .join(DgGroupOwner, DgGroupOwner.user_id == DgUser.id)
        .filter(DgGroupOwner.managed_group_id == managed_group.id)
        .filter(DgGroupOwner.source_type == "USER_OWNER")
        .order_by(DgUser.lower_username)
        .all()
    )
    user_owner_usernames = [r[0] for r in user_owner_rows]

    # Owning GROUP_OWNER groups
    group_owner_rows = (
        db.query(DgGroupOwnerGroup.owning_group_name)
        .filter(DgGroupOwnerGroup.managed_group_id == managed_group.id)
        .order_by(DgGroupOwnerGroup.lower_owning_group_name)
        .all()
    )
    owning_groups = [r[0] for r in group_owner_rows]

    # Legacy: groupOwners is a comma-separated string
    group_owners_group = ",".join(owning_groups)

    # Build userOwners objects (cached displayName + normalized profilePictureId)
    user_owners: List[Dict[str, Any]] = []
    if user_owner_usernames:
        user_owners = await asyncio.gather(*[_fetch_conf_user_cached(u) for u in user_owner_usernames])

    # Expand owning groups to members (paged)
    all_user_owners: List[Dict[str, Any]] = []
    if owning_groups:
        members_lists = await asyncio.gather(*[_fetch_conf_group_members_all(g) for g in owning_groups])
        for lst in members_lists:
            all_user_owners.extend(lst)

    # Include direct owners in allUserOwners (legacy behavior)
    all_user_owners.extend(user_owners)

    # Deduplicate by username
    dedup: Dict[str, Dict[str, Any]] = {}
    for u in all_user_owners:
        uname = u.get("username")
        if uname and uname not in dedup:
            dedup[uname] = u
    all_user_owners = list(dedup.values())

    return ORJSONResponse(
        content={
            "userOwners": user_owners,
            "groupOwners": group_owners_group,
            "allUserOwners": all_user_owners,
            "group": canonical_group_name,
        },
        status_code=200,
    )
    
class ConfGroupOwnerResponse(BaseModel):
    userOwners: List[UserOwnerResponse] = Field(default_factory=list)
    groupOwners: str = Field("", example="clean admins,cleans_leadership")
    allUserOwners: List[UserOwnerResponse] = Field(default_factory=list)
    group: str = Field(..., example="Cleans")
    