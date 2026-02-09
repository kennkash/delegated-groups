from pydantic import BaseModel, Field
from typing import List



class UserOwnerResponse(BaseModel):
    username: str = Field(..., example="janedoe1")
    userKey: str = Field(..., example="janedoe1")
    displayName: str = Field(..., example="Jane Doe")
    profilePictureId: str = Field(..., example="ownerId=janedoe1&avatarId=12104")
    avatarId:  str = Field(..., example="12104")
    ownerId:  str = Field(..., example="janedoe1")

class GroupOwnerResponse(BaseModel):
    userOwners: List[UserOwnerResponse] = Field(default_factory=list)
    groupOwners: str = Field(..., example="digital_solutions_admins")
    allUserOwners: List[UserOwnerResponse] = Field(default_factory=list)
    group: str = Field(..., example="digital_solutions")

    class Config:
        populate_by_name = True

@router.get(
    "/groupowners/{group}",
    status_code=200,
    summary="Get all group owners",
    response_model=GroupOwnerResponse,
)
async def get_owners(group: str = Path(..., example="digital_solutions")) -> ORJSONResponse:
    """
    get_owners is fetching jira owners by username and/or group

    Args:
        
        group (str): Name of jira group you want the owners of

    Returns
        ORJSONResponse:

            {
                "userOwners": [
                    {
                    "username": "janedoe1",
                    "userKey": "janedoe1",
                    "displayName": "Jane Doe",
                    "profilePictureId": "ownerId=janedoe1&avatarId=12104",
                    "avatarId": "12104",
                    "ownerId": "janedoe1"
                    }
                ],
                "groupOwners": "admins",
                "allUserOwners": [
                    {
                        "username": "janedoe1",
                        "userKey": "janedoe1",
                        "displayName": "Jane Doe",
                        "profilePictureId": "ownerId=janedoe1&avatarId=12104",
                        "avatarId": "12104",
                        "ownerId": "janedoe1"
                    },
                    {
                        "username": "janedoe2",
                        "userKey": "janedoe2",
                        "displayName": "Janie Doe",
                        "profilePictureId": "ownerId=janedoe2&avatarId=10335",
                        "avatarId": "10335",
                        "ownerId": "janedoe2"
                    },
                ],
                "group": "digital_solutions"
            }
    """
    groups = group.lower()
    try:
        query = session.query(
        jiraGroups.name,
        jiraGroups.del_group,
        jiraGroups.delegated
    ).where(jiraGroups.name == groups)
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
            api_path = f"{base_url}api/2/user?username={username}"
            d = external_api_session.get(api_path, headers=header)

            if d.status_code == 200:
                user_response = d.json()
                profile_picture_path = user_response["avatarUrls"]["48x48"]
                owner_id = None
                avatar_id = None

                if "?" in profile_picture_path:
                    base, query = profile_picture_path.split("?", 1)
                    query_parts = query.split("&")
                else:
                    query_parts = []
                    base = profile_picture_path

                params = {}
                for part in query_parts:
                    if "=" in part:
                        key, value = part.split("=", 1)
                        params[key] = value

                if "ownerId" in params:
                    owner_id = params["ownerId"]
                if "avatarId" in params:
                    avatar_id = params["avatarId"]

                profile_picture_id = f"ownerId={owner_id if owner_id is not None else 'undefined'}&avatarId={avatar_id if avatar_id is not None else 'None'}"

                if "displayName" in user_response and "active" in user_response and user_response["active"] is True:
                    user_owners_obj.append(
                        {
                            "username": username,
                            "userKey": user_response["key"],
                            "displayName": user_response["displayName"],
                            "profilePictureId": profile_picture_id,
                            "avatarId": avatar_id,
                            "ownerId": owner_id if owner_id is not None else "undefined"
                        }
                    )
                else:
                    user_owners_obj.append(
                        {
                            "username": username,
                            "userKey": user_response["key"],
                            "displayName": "Inactive User [X]",
                            "profilePictureId": profile_picture_id,
                            "avatarId": avatar_id,
                            "ownerId": owner_id if owner_id is not None else "undefined"
                        }
                    )
            else:
                continue 
            
        user_owners = user_owners_obj

    if group_owners_group:
        group_owner_groups = group_owners_group.split(',')

        all_user_owners = []
        for group in group_owner_groups:
            members = await get_members(group=group)
            group_members = members.body
            group_members_str = group_members.decode('utf-8')
            
            # Parse the JSON string to a dictionary
            group_members_json = json.loads(group_members_str)

            all_user_owners.extend(group_members_json)


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



  and then this is the get_members function that is called: 
@router.get(
    "/groupmembers",
    status_code=200,
    summary="Get all group members",
    response_model=JiraGroupMemberResponse,
)
async def get_members(group: str = Query(
            example="cleans",  # Shows as example, not default
            description="The name of the group to retrieve the members of"
        ) ) -> ORJSONResponse:
    """
    get_members is fetching jira group members when provided a group name

    Args:
        
        group (str): Name of jira group you want the members of

    Returns
        ORJSONResponse:

        [
            {
                "username": "adminjira",
                "userKey": "adminjira",
                "displayName": "adminjira",
                "profilePictureId": "ownerId=undefined&avatarId=10122",
                "avatarId": "10122",
                "ownerId": "undefined"
            },
        ]
    """
    bot_password = await getCreds(app)
    auth_token = bot_password
    header = {"Authorization": f"Bearer {auth_token}"}

    limit = 50
    start = 0
    member_names = []
    encoded_group = urllib.parse.quote(group, safe='')
    api_path = f"{base_url}api/2/group/member?groupname={encoded_group}&includeInactiveUsers=false"

    while True:
        api_path_with_params = f"{api_path}&maxResults={limit}&startAt={start}"
        r = external_api_session.get(api_path_with_params, headers=header)
        if r.status_code == 200:
            response_json = r.json()

            for result in response_json["values"]:
                profile_picture_path = result["avatarUrls"]["48x48"]

                owner_id = None
                avatar_id = None
                params = {}

                if "?" in profile_picture_path:
                    base, query = profile_picture_path.split("?", 1)
                    query_parts = query.split("&")
                else:
                    query_parts = []
                    base = profile_picture_path

                for part in query_parts:
                    if "=" in part:
                        key, value = part.split("=", 1)
                        params[key] = value

                if "ownerId" in params:
                    owner_id = params["ownerId"]
                if "avatarId" in params:
                    avatar_id = params["avatarId"]

                profile_picture_id = f"ownerId={owner_id if owner_id is not None else 'undefined'}&avatarId={avatar_id if avatar_id is not None else 'None'}"

                member_names.append({
                    "username": result["name"],
                    "userKey": result["key"],
                    "displayName": result["displayName"],
                    "profilePictureId": profile_picture_id,
                    "avatarId": avatar_id,
                    "ownerId": owner_id if owner_id is not None else "undefined"
                })

            if len(response_json["values"]) < limit:
                break

            start += limit
        else:
            continue
    return ORJSONResponse(content=member_names)
    return ORJSONResponse(content=response_json)
