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