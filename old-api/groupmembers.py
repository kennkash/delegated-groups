@router.get(
    "/groupmembers/{group}",
    status_code=200,
    summary="Get all group members",
    response_model=ConfGroupMemberResponse,
)
async def get_members(group: str = Path(..., example="cleans")) -> ORJSONResponse:
    """
    get_members is fetching Confluence group members when provided a group name

    Args:
        
        group (str): Name of Confluence group you want the members of

    Returns
        ORJSONResponse:

        [
            {
                "username": "icastillo2",
                "userKey": "e94190c96b2e6af0016bb4f63a7d1644",
                "displayName": "Ike Castillo",
                "profilePictureId": "11969190",
                "path": "/download/attachments/11969190/user-avatar"
            },
        ]
    """

    limit = 200
    start = 0
    member_names = []
    encoded_group = urllib.parse.quote(group, safe='')
    api_path = f"api/group/{encoded_group}/member"

    while True:
        api_path_with_params = f"{api_path}?limit={limit}&start={start}"
        response_json = await conf_client.get(api_path_with_params)
        if response_json:
            # response_json = r.json()

            for result in response_json["results"]:
                profile_picture_path = result.get("profilePicture", {}).get("path", "")
                profile_picture_id = None
                if profile_picture_path.startswith("/download/attachments/"):
                    components = profile_picture_path.split("/")
                    if len(components) >= 4 and components[2] == "attachments":
                        profile_picture_id = components[3]
                elif profile_picture_path == "/images/icons/profilepics/default.svg":
                    profile_picture_id = "default"
                path = result["profilePicture"]["path"]
                member_names.append(
                    {
                        "username": result["username"],
                        "userKey": result["userKey"],
                        "displayName": result["displayName"],
                        "profilePictureId": profile_picture_id,
                        "path": path,
                    }
                )

            if len(response_json["results"]) < limit:
                break

            start += limit
        else:
            continue
    return ORJSONResponse(content=member_names)
