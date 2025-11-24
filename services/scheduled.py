# delegated-groups/jobs/run_group_owner_sync.py

from typing import Iterable, Tuple, Optional

from delegated-groups.services.dg_service import sync_all_group_owners


def fetch_members_for_group(app: str, owning_group_name: str) -> Iterable[Tuple[str, Optional[str]]]:
    """
    Given an app ('jira' or 'confluence') and an owning group name,
    return the CURRENT members of that group as (username, email) tuples.

    You need to implement this using:
      - your Jira/Confluence SQL Server queries, OR
      - Jira/Confluence REST APIs.

    Example shape:
        return [
            ("kkashmiry0641", "k@example.com"),
            ("sre1", "sre1@example.com"),
            ("sre2", None),
        ]
    """
    # TODO: implement from your environment.
    # Pseudocode example using SQL Server:
    #
    # if app == "jira":
    #     # run a SQL query against JiraProd to get members of `owning_group_name`
    #     # using your existing cwd_user/cwd_group/cwd_membership knowledge
    #     ...
    # elif app == "confluence":
    #     # similar query against Confluence DB
    #     ...
    # else:
    #     return []
    #
    # For now, just raise to remind yourself to fill this in:
    raise NotImplementedError("fetch_members_for_group() must be implemented.")


def main():
    # This will:
    #  1. discover all (app, delegated_group, via_group_name) with GROUP_OWNER rows
    #  2. for each, call fetch_members_for_group(app, via_group_name)
    #  3. sync dg_group_owner rows to match current membership
    sync_all_group_owners(fetch_members_for_group)


if __name__ == "__main__":
    main()
















## Jira
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

## Jira Response
{
    "self": "https://jira.samsungaustin.com/rest/api/2/group/member?includeInactiveUsers=false&maxResults=50&groupname=jira-administrators&startAt=0",
    "maxResults": 50,
    "startAt": 0,
    "total": 13,
    "isLast": true,
    "values": [
        {
            "self": "https://jira.samsungaustin.com/rest/api/2/user?username=adminjira",
            "name": "adminjira",
            "key": "adminjira",
            "emailAddress": "adminjira@samsung.com",
            "avatarUrls": {
                "48x48": "https://jira.samsungaustin.com/secure/useravatar?avatarId=10122",
                "24x24": "https://jira.samsungaustin.com/secure/useravatar?size=small&avatarId=10122",
                "16x16": "https://jira.samsungaustin.com/secure/useravatar?size=xsmall&avatarId=10122",
                "32x32": "https://jira.samsungaustin.com/secure/useravatar?size=medium&avatarId=10122"
            },
            "displayName": "adminjira",
            "active": true,
            "timeZone": "CST6CDT"
        },
        {
            "self": "https://jira.samsungaustin.com/rest/api/2/user?username=atlassianbot",
            "name": "atlassianbot",
            "key": "atlassianbot",
            "emailAddress": "test@tester.com",
            "avatarUrls": {
                "48x48": "https://jira.samsungaustin.com/secure/useravatar?ownerId=atlassianbot&avatarId=14201",
                "24x24": "https://jira.samsungaustin.com/secure/useravatar?size=small&ownerId=atlassianbot&avatarId=14201",
                "16x16": "https://jira.samsungaustin.com/secure/useravatar?size=xsmall&ownerId=atlassianbot&avatarId=14201",
                "32x32": "https://jira.samsungaustin.com/secure/useravatar?size=medium&ownerId=atlassianbot&avatarId=14201"
            },
            "displayName": "Atlassian Bot",
            "active": true,
            "timeZone": "CST6CDT"
        },
        {
            "self": "https://jira.samsungaustin.com/rest/api/2/user?username=automationbot",
            "name": "automationbot",
            "key": "automationbot",
            "emailAddress": "richardson.r@demo.samsung.com",
            "avatarUrls": {
                "48x48": "https://jira.samsungaustin.com/secure/useravatar?avatarId=10341",
                "24x24": "https://jira.samsungaustin.com/secure/useravatar?size=small&avatarId=10341",
                "16x16": "https://jira.samsungaustin.com/secure/useravatar?size=xsmall&avatarId=10341",
                "32x32": "https://jira.samsungaustin.com/secure/useravatar?size=medium&avatarId=10341"
            },
            "displayName": "Automation Bot",
            "active": true,
            "timeZone": "CST6CDT"
        },
        {
            "self": "https://jira.samsungaustin.com/rest/api/2/user?username=cloudbot",
            "name": "cloudbot",
            "key": "cloudbot",
            "emailAddress": "cloudbot@tester.com",
            "avatarUrls": {
                "48x48": "https://jira.samsungaustin.com/secure/useravatar?ownerId=cloudbot&avatarId=16506",
                "24x24": "https://jira.samsungaustin.com/secure/useravatar?size=small&ownerId=cloudbot&avatarId=16506",
                "16x16": "https://jira.samsungaustin.com/secure/useravatar?size=xsmall&ownerId=cloudbot&avatarId=16506",
                "32x32": "https://jira.samsungaustin.com/secure/useravatar?size=medium&ownerId=cloudbot&avatarId=16506"
            },
            "displayName": "ATL Cloud Bot",
            "active": true,
            "timeZone": "CST6CDT"
        },
        {
            "self": "https://jira.samsungaustin.com/rest/api/2/user?username=dmcbot",
            "name": "dmcbot",
            "key": "dmcbot",
            "emailAddress": "dmcbot@samsung.com",
            "avatarUrls": {
                "48x48": "https://jira.samsungaustin.com/secure/useravatar?ownerId=dmcbot&avatarId=17412",
                "24x24": "https://jira.samsungaustin.com/secure/useravatar?size=small&ownerId=dmcbot&avatarId=17412",
                "16x16": "https://jira.samsungaustin.com/secure/useravatar?size=xsmall&ownerId=dmcbot&avatarId=17412",
                "32x32": "https://jira.samsungaustin.com/secure/useravatar?size=medium&ownerId=dmcbot&avatarId=17412"
            },
            "displayName": "DMC Bot",
            "active": true,
            "timeZone": "CST6CDT"
        },
        {
            "self": "https://jira.samsungaustin.com/rest/api/2/user?username=dmoody",
            "name": "dmoody",
            "key": "dmoody",
            "emailAddress": "d.moody@samsung.com",
            "avatarUrls": {
                "48x48": "https://jira.samsungaustin.com/secure/useravatar?ownerId=dmoody&avatarId=12104",
                "24x24": "https://jira.samsungaustin.com/secure/useravatar?size=small&ownerId=dmoody&avatarId=12104",
                "16x16": "https://jira.samsungaustin.com/secure/useravatar?size=xsmall&ownerId=dmoody&avatarId=12104",
                "32x32": "https://jira.samsungaustin.com/secure/useravatar?size=medium&ownerId=dmoody&avatarId=12104"
            },
            "displayName": "Daniel Drummond Moody",
            "active": true,
            "timeZone": "CST6CDT"
        },
        {
            "self": "https://jira.samsungaustin.com/rest/api/2/user?username=icastillo2",
            "name": "icastillo2",
            "key": "icastillo2",
            "emailAddress": "i.castillo2@samsung.com",
            "avatarUrls": {
                "48x48": "https://jira.samsungaustin.com/secure/useravatar?ownerId=icastillo2&avatarId=13121",
                "24x24": "https://jira.samsungaustin.com/secure/useravatar?size=small&ownerId=icastillo2&avatarId=13121",
                "16x16": "https://jira.samsungaustin.com/secure/useravatar?size=xsmall&ownerId=icastillo2&avatarId=13121",
                "32x32": "https://jira.samsungaustin.com/secure/useravatar?size=medium&ownerId=icastillo2&avatarId=13121"
            },
            "displayName": "Ike Castillo",
            "active": true,
            "timeZone": "CST6CDT"
        },
        {
            "self": "https://jira.samsungaustin.com/rest/api/2/user?username=jiralocaladmin",
            "name": "jiralocaladmin",
            "key": "rrlocaladmin",
            "emailAddress": "sas.jira@samsung.com",
            "avatarUrls": {
                "48x48": "https://jira.samsungaustin.com/secure/useravatar?avatarId=10341",
                "24x24": "https://jira.samsungaustin.com/secure/useravatar?size=small&avatarId=10341",
                "16x16": "https://jira.samsungaustin.com/secure/useravatar?size=xsmall&avatarId=10341",
                "32x32": "https://jira.samsungaustin.com/secure/useravatar?size=medium&avatarId=10341"
            },
            "displayName": "Local Admin User",
            "active": true,
            "timeZone": "CST6CDT"
        },
        {
            "self": "https://jira.samsungaustin.com/rest/api/2/user?username=jlevy",
            "name": "jlevy",
            "key": "jlevy",
            "emailAddress": "jon.levy@samsung.com",
            "avatarUrls": {
                "48x48": "https://jira.samsungaustin.com/secure/useravatar?avatarId=10349",
                "24x24": "https://jira.samsungaustin.com/secure/useravatar?size=small&avatarId=10349",
                "16x16": "https://jira.samsungaustin.com/secure/useravatar?size=xsmall&avatarId=10349",
                "32x32": "https://jira.samsungaustin.com/secure/useravatar?size=medium&avatarId=10349"
            },
            "displayName": "Jonathan Levy",
            "active": true,
            "timeZone": "CST6CDT"
        },
        {
            "self": "https://jira.samsungaustin.com/rest/api/2/user?username=kkashmiry0641",
            "name": "kkashmiry0641",
            "key": "kkashmiry0641",
            "emailAddress": "k.kashmiry@samsung.com",
            "avatarUrls": {
                "48x48": "https://jira.samsungaustin.com/secure/useravatar?ownerId=kkashmiry0641&avatarId=17208",
                "24x24": "https://jira.samsungaustin.com/secure/useravatar?size=small&ownerId=kkashmiry0641&avatarId=17208",
                "16x16": "https://jira.samsungaustin.com/secure/useravatar?size=xsmall&ownerId=kkashmiry0641&avatarId=17208",
                "32x32": "https://jira.samsungaustin.com/secure/useravatar?size=medium&ownerId=kkashmiry0641&avatarId=17208"
            },
            "displayName": "Kennedy Kashmiry",
            "active": true,
            "timeZone": "CST6CDT"
        },
        {
            "self": "https://jira.samsungaustin.com/rest/api/2/user?username=ksadmin",
            "name": "ksadmin",
            "key": "ksadmin",
            "emailAddress": "ksadmin@samsung.com",
            "avatarUrls": {
                "48x48": "https://jira.samsungaustin.com/secure/useravatar?avatarId=10122",
                "24x24": "https://jira.samsungaustin.com/secure/useravatar?size=small&avatarId=10122",
                "16x16": "https://jira.samsungaustin.com/secure/useravatar?size=xsmall&avatarId=10122",
                "32x32": "https://jira.samsungaustin.com/secure/useravatar?size=medium&avatarId=10122"
            },
            "displayName": "ksadmin",
            "active": true,
            "timeZone": "CST6CDT"
        },
        {
            "self": "https://jira.samsungaustin.com/rest/api/2/user?username=spandeti2572",
            "name": "spandeti2572",
            "key": "spandeti2572",
            "emailAddress": "s.pandeti@samsung.com",
            "avatarUrls": {
                "48x48": "https://jira.samsungaustin.com/secure/useravatar?ownerId=spandeti2572&avatarId=12802",
                "24x24": "https://jira.samsungaustin.com/secure/useravatar?size=small&ownerId=spandeti2572&avatarId=12802",
                "16x16": "https://jira.samsungaustin.com/secure/useravatar?size=xsmall&ownerId=spandeti2572&avatarId=12802",
                "32x32": "https://jira.samsungaustin.com/secure/useravatar?size=medium&ownerId=spandeti2572&avatarId=12802"
            },
            "displayName": "Sramanth Varma Pandeti",
            "active": true,
            "timeZone": "CST6CDT"
        },
        {
            "self": "https://jira.samsungaustin.com/rest/api/2/user?username=sramadmin",
            "name": "sramadmin",
            "key": "sramadmin",
            "emailAddress": "sramadmin@samsung.com",
            "avatarUrls": {
                "48x48": "https://jira.samsungaustin.com/secure/useravatar?avatarId=10122",
                "24x24": "https://jira.samsungaustin.com/secure/useravatar?size=small&avatarId=10122",
                "16x16": "https://jira.samsungaustin.com/secure/useravatar?size=xsmall&avatarId=10122",
                "32x32": "https://jira.samsungaustin.com/secure/useravatar?size=medium&avatarId=10122"
            },
            "displayName": "sramadmin",
            "active": true,
            "timeZone": "CST6CDT"
        }
    ]
}

## Confluence
 bot_password = await getCreds(app)

auth_token = bot_password
header = {"Authorization": f"Bearer {auth_token}"}
limit = 200
start = 0
member_names = []
encoded_group = urllib.parse.quote(group, safe='')
api_path = f"{base_url}api/group/{encoded_group}/member"

while True:
    api_path_with_params = f"{api_path}?limit={limit}&start={start}"
    r = external_api_session.get(api_path_with_params, headers=header)
    if r.status_code == 200:
        response_json = r.json()


# Confluence Response
{
    "results": [
        {
            "type": "known",
            "username": "atlassianadmin",
            "userKey": "e941906c88c447470189b1cbd118013e",
            "profilePicture": {
                "path": "/images/icons/profilepics/default.svg",
                "width": 48,
                "height": 48,
                "isDefault": true
            },
            "displayName": "atlassian",
            "_links": {
                "self": "https://confluence.samsungaustin.com/rest/api/user?key=e941906c88c447470189b1cbd118013e"
            },
            "_expandable": {
                "status": ""
            }
        },
        {
            "type": "known",
            "username": "atlassianbot",
            "userKey": "e941906c88c44747018944dd035f0087",
            "profilePicture": {
                "path": "/download/attachments/193950586/user-avatar",
                "width": 48,
                "height": 48,
                "isDefault": false
            },
            "displayName": "Atlassian Bot",
            "_links": {
                "self": "https://confluence.samsungaustin.com/rest/api/user?key=e941906c88c44747018944dd035f0087"
            },
            "_expandable": {
                "status": ""
            }
        },
        {
            "type": "known",
            "username": "cloudbot",
            "userKey": "e941909b94f63f04019500af52ed0002",
            "profilePicture": {
                "path": "/download/attachments/533079210/user-avatar",
                "width": 48,
                "height": 48,
                "isDefault": false
            },
            "displayName": "ATL Cloud Bot",
            "_links": {
                "self": "https://confluence.samsungaustin.com/rest/api/user?key=e941909b94f63f04019500af52ed0002"
            },
            "_expandable": {
                "status": ""
            }
        },
        {
            "type": "known",
            "username": "dmcbot",
            "userKey": "e94190b89a7e6817019a989603cd0023",
            "profilePicture": {
                "path": "/download/attachments/785800018/user-avatar",
                "width": 48,
                "height": 48,
                "isDefault": false
            },
            "displayName": "DMC Bot",
            "_links": {
                "self": "https://confluence.samsungaustin.com/rest/api/user?key=e94190b89a7e6817019a989603cd0023"
            },
            "_expandable": {
                "status": ""
            }
        },
        {
            "type": "known",
            "username": "dmoody",
            "userKey": "e94190c96b2e6af0016bb4f635e911f1",
            "profilePicture": {
                "path": "/download/attachments/11968083/user-avatar",
                "width": 48,
                "height": 48,
                "isDefault": false
            },
            "displayName": "Daniel Drummond Moody",
            "_links": {
                "self": "https://confluence.samsungaustin.com/rest/api/user?key=e94190c96b2e6af0016bb4f635e911f1"
            },
            "_expandable": {
                "status": ""
            }
        },
        {
            "type": "known",
            "username": "icastillo2",
            "userKey": "e94190c96b2e6af0016bb4f63a7d1644",
            "profilePicture": {
                "path": "/download/attachments/11969190/user-avatar",
                "width": 48,
                "height": 48,
                "isDefault": false
            },
            "displayName": "Ike Castillo",
            "_links": {
                "self": "https://confluence.samsungaustin.com/rest/api/user?key=e94190c96b2e6af0016bb4f63a7d1644"
            },
            "_expandable": {
                "status": ""
            }
        },
        {
            "type": "known",
            "username": "kkashmiry0641",
            "userKey": "e941906c813ef29d01818c3363ce007e",
            "profilePicture": {
                "path": "/download/attachments/96107252/user-avatar",
                "width": 48,
                "height": 48,
                "isDefault": false
            },
            "displayName": "Kennedy Kashmiry",
            "_links": {
                "self": "https://confluence.samsungaustin.com/rest/api/user?key=e941906c813ef29d01818c3363ce007e"
            },
            "_expandable": {
                "status": ""
            }
        },
        {
            "type": "known",
            "username": "ksadmin",
            "userKey": "e941906c9328a7c40193bcb443da0029",
            "profilePicture": {
                "path": "/images/icons/profilepics/default.svg",
                "width": 48,
                "height": 48,
                "isDefault": true
            },
            "displayName": "ksadmin",
            "_links": {
                "self": "https://confluence.samsungaustin.com/rest/api/user?key=e941906c9328a7c40193bcb443da0029"
            },
            "_expandable": {
                "status": ""
            }
        },
        {
            "type": "known",
            "username": "rrlocaladmin",
            "userKey": "e94190c96fab196e017020a8d9a00005",
            "profilePicture": {
                "path": "/images/icons/profilepics/default.svg",
                "width": 48,
                "height": 48,
                "isDefault": true
            },
            "displayName": "RR Local Admin Confluence",
            "_links": {
                "self": "https://confluence.samsungaustin.com/rest/api/user?key=e94190c96fab196e017020a8d9a00005"
            },
            "_expandable": {
                "status": ""
            }
        },
        {
            "type": "known",
            "username": "spandeti2572",
            "userKey": "e941906c7f2cd2e301802171edf901dc",
            "profilePicture": {
                "path": "/download/attachments/88368665/user-avatar",
                "width": 48,
                "height": 48,
                "isDefault": false
            },
            "displayName": "Sramanth Varma Pandeti",
            "_links": {
                "self": "https://confluence.samsungaustin.com/rest/api/user?key=e941906c7f2cd2e301802171edf901dc"
            },
            "_expandable": {
                "status": ""
            }
        },
        {
            "type": "known",
            "username": "sramadmin",
            "userKey": "e941906c8d9e8090018da3235e8e0000",
            "profilePicture": {
                "path": "/images/icons/profilepics/default.svg",
                "width": 48,
                "height": 48,
                "isDefault": true
            },
            "displayName": "sramadmin",
            "_links": {
                "self": "https://confluence.samsungaustin.com/rest/api/user?key=e941906c8d9e8090018da3235e8e0000"
            },
            "_expandable": {
                "status": ""
            }
        }
    ],
    "start": 0,
    "limit": 200,
    "size": 11,
    "_links": {
        "self": "https://confluence.samsungaustin.com/rest/api/group/confluence-administrators/member",
        "base": "https://confluence.samsungaustin.com",
        "context": ""
    }
}
