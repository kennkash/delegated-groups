
# ----------------------------
# Cached Confluence user fetch
# ----------------------------
@cache(expire=60 * 30, namespace="conf_user")  # 30 minutes
async def _fetch_conf_user_cached(username: str) -> Dict[str, Any]:
    """
    ONE Confluence call total:
      /rest/api/user?username=<username>

    Returns legacy-shaped:
      { username, displayName, profilePictureId }
    """
    enc_user = urllib.parse.quote(username, safe="")
    try:
        data = await conf_client.get(f"api/user?username={enc_user}")
    except Exception:
        return {"username": username, "displayName": "Inactive User [X]", "profilePictureId": "default"}

    display = data.get("displayName") or "Inactive User [X]"
    prof_id = ProfilePicFetcher.normalize_conf_profile_picture_id(data)
    return {"username": username, "displayName": display, "profilePictureId": prof_id}


# -----------------------------------------
# Expand group -> members (paged, no extra calls)
# -----------------------------------------
async def _fetch_conf_group_members_all(group_name: str) -> List[Dict[str, Any]]:
    """
    Uses Confluence:
      /rest/api/group/<group>/member?limit=200&start=0...

    Returns list of legacy-shaped:
      { username, displayName, profilePictureId }
    """
    limit = 200
    start = 0
    out: List[Dict[str, Any]] = []

    enc_group = urllib.parse.quote(group_name, safe="")
    api_path = f"api/group/{enc_group}/member"

    while True:
        payload = await conf_client.get(f"{api_path}?limit={limit}&start={start}")
        results = (payload or {}).get("results", []) or []

        for r in results:
            uname = r.get("username")
            if not uname:
                continue
            out.append(
                {
                    "username": uname,
                    "displayName": r.get("displayName") or "Inactive User [X]",
                    # IMPORTANT: normalize from the member payload (it has profilePicture.path)
                    "profilePictureId": ProfilePicFetcher.normalize_conf_profile_picture_id(r),
                }
            )

        if len(results) < limit:
            break
        start += limit

    return out


def _dedupe_users_by_username(users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    dedup: Dict[str, Dict[str, Any]] = {}
    for u in users:
        uname = u.get("username")
        if uname and uname not in dedup:
            dedup[uname] = u
    return list(dedup.values())


# ----------------------------
# UPDATED: /groupowners/{group}
# ----------------------------
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

    # 1) Is it delegated? (DB-backed)
    managed_group = (
        db.query(DgManagedGroup)
        .filter(DgManagedGroup.app == "confluence")
        .filter(DgManagedGroup.lower_group_name == group_lower)
        .one_or_none()
    )

    # Keep legacy "not delegated" keys
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

    # 2) Direct USER_OWNER users (from DB)
    user_owner_rows = (
        db.query(DgUser.username)
        .join(DgGroupOwner, DgGroupOwner.user_id == DgUser.id)
        .filter(DgGroupOwner.managed_group_id == managed_group.id)
        .filter(DgGroupOwner.source_type == "USER_OWNER")
        .order_by(DgUser.lower_username)
        .all()
    )
    direct_owner_usernames = [r[0] for r in user_owner_rows]

    # 3) GROUP_OWNER owning groups (from DB)
    group_owner_rows = (
        db.query(DgGroupOwnerGroup.owning_group_name)
        .filter(DgGroupOwnerGroup.managed_group_id == managed_group.id)
        .order_by(DgGroupOwnerGroup.lower_owning_group_name)
        .all()
    )
    owning_groups = [r[0] for r in group_owner_rows]

    # legacy: comma-separated string
    group_owners_str = ",".join(owning_groups)

    # 4) Build userOwners (cached, 1 call each)
    user_owners: List[Dict[str, Any]] = []
    if direct_owner_usernames:
        user_owners = await asyncio.gather(*[_fetch_conf_user_cached(u) for u in direct_owner_usernames])

    # 5) Expand owning groups to users (paged, NO per-user calls)
    inherited_users: List[Dict[str, Any]] = []
    if owning_groups:
        member_lists = await asyncio.gather(*[_fetch_conf_group_members_all(g) for g in owning_groups])
        for lst in member_lists:
            inherited_users.extend(lst)

    # 6) allUserOwners = inherited + direct, deduped
    all_user_owners = _dedupe_users_by_username(inherited_users + user_owners)

    # 7) Return in the exact frontend shape
    return ORJSONResponse(
        content={
            "userOwners": user_owners,
            "groupOwners": group_owners_str,
            "allUserOwners": all_user_owners,
            "group": canonical_group_name,
        },
        status_code=200,
        )