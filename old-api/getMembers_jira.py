@router.get(
    "/groupmembers",
    status_code=200,
    summary="Get all group members",
    response_model=JiraGroupMemberResponse,
)
async def get_members(
    group: str = Query(
        example="cleans",
        description="The name of the group to retrieve the members of"
    )
) -> ORJSONResponse:
    bot_password = await getCreds(app)
    auth_token = bot_password
    header = {"Authorization": f"Bearer {auth_token}"}

    limit = 50
    start = 0
    member_names = []

    encoded_group = urllib.parse.quote(group, safe="")
    api_base = f"{base_url}api/2/group/member?groupname={encoded_group}&includeInactiveUsers=false"

    # Safety cap to prevent infinite loops if Jira behaves unexpectedly
    max_pages = 500  # 500 * 50 = 25,000 users cap
    page_count = 0

    while True:
        page_count += 1
        if page_count > max_pages:
            # better than hanging forever
            break

        api_path = f"{api_base}&maxResults={limit}&startAt={start}"
        r = external_api_session.get(api_path, headers=header)

        if r.status_code != 200:
            # avoid infinite 'continue' loops on errors
            break

        response_json = r.json()
        values = response_json.get("values", []) or []

        for result in values:
            profile_picture_id_qs = ProfilePicFetcher.normalize_jira_profile_picture_id(result)
            parts = ProfilePicFetcher.jira_avatar_parts_from_profile_picture_id(profile_picture_id_qs)

            member_names.append({
                "username": result.get("name"),
                "userKey": result.get("key"),
                "displayName": result.get("displayName"),
                "profilePictureId": parts["profilePictureId"],
                "avatarId": parts["avatarId"],
                "ownerId": parts["ownerId"],
            })

        # ✅ Preferred Jira pagination flags if present
        if response_json.get("isLast") is True:
            break

        total = response_json.get("total")
        max_results = response_json.get("maxResults", limit)
        start_at = response_json.get("startAt", start)

        if isinstance(total, int) and (start_at + max_results) >= total:
            break

        # Fallback: old behavior
        if len(values) < limit:
            break

        start += limit

    return ORJSONResponse(content=member_names)
