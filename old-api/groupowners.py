@router.get(
    "/groupowners/{group}",
    status_code=200,
    summary="Get all group owners",
    response_model=ConfGroupOwnerResponse,
)
async def get_owners(group: str = Path(..., example="Cleans")) -> ORJSONResponse:
    """
    get_owners is fetching Confluence owners by username and/or group

    Args:
        
        group (str): Name of Confluence group you want to view owners of

    Returns
        ORJSONResponse:

            {
                "userOwners": [
                    {
                    "username": "icastillo2",
                    "displayName": "Ike Castillo",
                    "profilePictureId": "11969190"
                    }
                ],
                "groupOwners": "clean admins,cleans_leadership",
                "allUserOwners": [
                    {
                    "username": "icastillo2",
                    "displayName": "Ike Castillo",
                    "profilePictureId": "11969190"
                    },
                    {
                    "username": "spandeti2572",
                    "displayName": "Sramanth Varma Pandeti",
                    "profilePictureId": "88368665"
                    },
                    {
                    "username": "janedoe1",
                    "displayName": "Jane Doe",
                    "profilePictureId": "default"
                    },
                ],
                "group": "Cleans"
            }
    """
    groups = group.lower()
    try:
        query = session.query(
        confluenceGroups.name,
        confluenceGroups.del_group,
        confluenceGroups.delegated
    ).where(confluenceGroups.name == groups)
        result = session.execute(query)
        df2 = pd.DataFrame(result.fetchall(), columns=result.keys())
    except Exception as e:
        session.rollback()
        print(e)
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        session.close()

    delegated_groups_dict = df2

    if not delegated_groups_dict['delegated'].all():
        return ORJSONResponse(
            content={
                "message": "Not a delegated group",
                "allUserOwners": "",
                "group": group,
                "groupOwners": "",
                "userOwners": "",
            },
            status_code=200,
        )

    # Find the correct capitalization version of the group name
    correct_group_name = delegated_groups_dict.iloc[0]['del_group']
    encoded_group = urllib.parse.quote(correct_group_name, safe='')
    
    bot_password = await getCreds(app)
    auth_token = bot_password
    header = {"Authorization": f"Bearer {auth_token}"}
    api_path = (
        f"{base_url}wittified/delegated-groups/1.0/delegation/getGroup/{encoded_group}"
    )
    u = external_api_session.get(api_path, headers=header)
    response_json = u.json()

    group_owners_group = response_json.get("groupOwners", "")

    user_owners = response_json.get("userOwners", "")

    if user_owners:
        user_owners_list = user_owners.split(",")
        user_owners_obj = []

        for username in user_owners_list:
            api_path = f"{base_url}api/user?username={username}"
            d = external_api_session.get(api_path, headers=header)
            if d.status_code == 200:
                user_response = d.json()

                profile_picture_path = user_response.get("profilePicture", {}).get("path", "")
                profile_picture_id = None
                if profile_picture_path.startswith("/download/attachments/"):
                    components = profile_picture_path.split("/")
                    if len(components) >= 4 and components[2] == "attachments":
                        profile_picture_id = components[3]
                elif profile_picture_path == "/images/icons/profilepics/default.svg":
                    profile_picture_id = "default"

                if "displayName" in user_response:
                    user_owners_obj.append(
                        {"username": username, "displayName": user_response["displayName"], "profilePictureId": profile_picture_id}
                    )
                else:
                    user_owners_obj.append({"username": username, "displayName": "Inactive User [X]", "profilePictureId": "default"})
            else:
                continue

        user_owners = user_owners_obj

    if group_owners_group:
        group_owner_groups = group_owners_group.split(',')

        all_user_owners = []
        for group in group_owner_groups:
            api_path = f"{base_url}api/group/{group}/member"
            response = external_api_session.get(api_path, headers=header)
            all_user_owners.extend([
                {
                    "username": user.get("username"),
                    "displayName": user.get("displayName"),
                    "profilePictureId": (
                        "default" if user.get("profilePicture", {}).get("path", "") == "/images/icons/profilepics/default.svg"
                        else None if not user.get("profilePicture", {}).get("path", "").startswith("/download/attachments/")
                        else user.get("profilePicture", {}).get("path", "").split("/")[3]
                    ),
                }
                for user in response.json().get("results", [])
            ])

        all_user_owners = list(dict((user["username"], user) for user in all_user_owners).values())

        if user_owners:
            all_user_owners.extend(user_owners)
            all_user_owners = list(dict((user["username"], user) for user in all_user_owners).values())

    else:
        all_user_owners = user_owners

    # Reorder the response to put "AllUserOwners" before "group"
    response_json = {
        "userOwners": user_owners,
        "groupOwners": group_owners_group,
        "allUserOwners": all_user_owners,
        "group": response_json.get("group"),
    }

    return ORJSONResponse(content=response_json)
