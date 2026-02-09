@router.get("/groups/owners")
async def get_delegated_group_owners(
    app: str,
    group_name: str,
    db: Session = Depends(get_db),
):
    """
    get_delegated_group_owners returns the direct owners for a delegated group (DB-backed).

    This endpoint returns:
    - USER_OWNER: users directly assigned as owners of the delegated group
    - GROUP_OWNER: owning group names that grant inherited ownership
      (membership expansion handled elsewhere)

    <details><summary><span>Parameters</span></summary>
    | Name | Type | Description |
    |------|------|-------------|
    | `app` | `str` | Application name: `jira` or `confluence` |
    | `group_name` | `str` | Delegated group name (original name, any characters allowed) |
    </details>

    <details><summary><span>Returns</span></summary>

    A JSON object containing:

    * `app` – `jira` or `confluence`
    * `group_name` – delegated group name
    * `user_owners` – list of direct user owners:
        * `username`
        * `email`
    * `group_owners` – list of owning group names
    </details>
    """
    app_lower = app.lower()
    if app_lower not in {"jira", "confluence"}:
        raise HTTPException(status_code=400, detail="app must be 'jira' or 'confluence'")

    managed_group = (
        db.query(DgManagedGroup)
        .filter(DgManagedGroup.app == app_lower)
        .filter(DgManagedGroup.lower_group_name == group_name.lower())
        .one_or_none()
    )
    if not managed_group:
        raise HTTPException(status_code=404, detail="Delegated group not found")

    # USER_OWNER → users
    user_owner_rows = (
        db.query(DgUser.username, DgUser.email)
        .join(DgGroupOwner, DgGroupOwner.user_id == DgUser.id)
        .filter(DgGroupOwner.managed_group_id == managed_group.id)
        .filter(DgGroupOwner.source_type == "USER_OWNER")
        .order_by(DgUser.lower_username)
        .all()
    )
    user_owners = [{"username": u, "email": e} for (u, e) in user_owner_rows]
    
    
    async def _populate_profile(user: Dict[str, Any], app: str) -> None:
        """
        Mutates the supplied ``user`` dict, adding a ``profilePictureId`` field
        that contains the URL (Jira) **or** the path (Confluence) of the user's
        avatar image.

        Parameters
        ----------
        user: dict
            Must contain a ``username`` key.
        app: str
            Either ``'jira'`` or ``'confluence'`` (any other value falls back to
            the Confluence helper – you can tighten the validation if you wish).

        Returns
        -------
        None – the ``user`` dict is mutated in‑place.
        """

        try:
            # ------------------------------------------------------------------
            # 1️⃣  Build the fetcher and call the appropriate method
            # ------------------------------------------------------------------
            fetcher = ProfilePicFetcher(user["username"])

            if app.lower() == "jira":
                # JIRA returns the **full avatar URL** (48×48)
                avatar = await fetcher.fetchJ_profpic()
            else:
                # Confluence returns the **relative path** inside the instance
                avatar = await fetcher.fetchC_profpic()

            # ------------------------------------------------------------------
            # 2️⃣  Store the result in the payload
            # ------------------------------------------------------------------
            # The original code used ``profilePictureId`` → keep that naming.
            user["profilePictureId"] = avatar

        except Exception as exc:          # catches HTTPException and any other error
            # --------------------------------------------------------------
            # Log the problem but keep the request alive – just like the
            # original implementation.
            # --------------------------------------------------------------
            logger.warning(
                f"Unable to fetch {'Jira' if app.lower() == 'jira' else 'Confluence'} "
                f"profile picture for {user.get('username')}: {exc}"
            )
            user["profilePictureId"] = None

    # Fire them off in parallel – this is usually much faster than a
    # simple `for` loop with `await` inside.
    await asyncio.gather(*[_populate_profile(u, app_lower) for u in user_owners])

    # GROUP_OWNER → owning groups
    group_owner_rows = (
        db.query(DgGroupOwnerGroup.owning_group_name)
        .filter(DgGroupOwnerGroup.managed_group_id == managed_group.id)
        .order_by(DgGroupOwnerGroup.lower_owning_group_name)
        .all()
    )
    group_owners = [r[0] for r in group_owner_rows]

    return {
        "app": managed_group.app,
        "group_name": managed_group.group_name,
        "user_owners": user_owners,
        "group_owners": group_owners,
    }






# profile_pic_fetcher.py
import re
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from .external_api.jiraRequests import JiraAPIClient
from .external_api.confRequests import ConfAPIClient


class ProfilePicFetcher:
    """
    Helper that fetches a user's avatar information from JIRA or Confluence
    and returns a *clean* string according to the business rules:

    * JIRA → only the part **after** the first '?' of the 48×48 avatar URL.
    If the avatar cannot be located the function returns the default
    query string ``avatarId=10122``.
    * Confluence → normalized picture identifier:
        - ``/download/attachments/<num>/user-avatar`` → ``<num>``
        - ``/images/icons/profilepics/default.svg`` → ``default``
        - any other path → the original path
    If the picture cannot be located the function returns the literal
    string ``default``.
    """

    # ------------------------------------------------------------------ #
    #  Constructor
    # ------------------------------------------------------------------ #
    def __init__(self, username: str):
        self._jira_client = JiraAPIClient()
        self._conf_client = ConfAPIClient()
        self.username = username

        # End‑points are relative; the client objects already contain the base URL
        self.__jira_api_path = f"api/2/user/search?username={self.username}"
        self.__conf_api_path = f"api/user?username={self.username}"

    # ------------------------------------------------------------------ #
    #  Private helper methods – pure functions, easy to unit‑test
    # ------------------------------------------------------------------ #
    @staticmethod
    def _extract_jira_avatar(data: List[Dict[str, Any]]) -> Optional[str]:
        """JIRA returns a list; take the first element's 48×48 avatar URL."""
        if not data:
            return None
        return data[0].get("avatarUrls", {}).get("48x48")

    @staticmethod
    def _strip_query(url: str) -> str:
        """
        Return everything after the first '?' in ``url``.
        If no '?' is present we simply return the original string.
        """
        _before, sep, after = url.partition("?")
        return after if sep else url

    @staticmethod
    def _extract_conf_path(data: Dict[str, Any]) -> Optional[str]:
        """Pull the raw ``profilePicture.path`` value from the Confluence payload."""
        return data.get("profilePicture", {}).get("path")

    @staticmethod
    def _normalize_conf_path(raw_path: str) -> str:
        """
        Apply Confluence‑specific normalisation rules:

        1. ``/download/attachments/<num>/user-avatar`` → ``<num>``
        2. ``/images/icons/profilepics/default.svg``   → ``default``
        3. Anything else                               → original ``raw_path``
        """
        # Rule 1 – numeric folder before “user-avatar”
        m = re.search(r"/download/attachments/(\d+)/user-avatar", raw_path)
        if m:
            return m.group(1)

        # Rule 2 – default avatar SVG
        if raw_path.endswith("/default.svg"):
            return "default"

        # Fallback – keep the path unchanged
        return raw_path

    # ------------------------------------------------------------------ #
    #  Public async API
    # ------------------------------------------------------------------ #
    async def fetchJ_profpic(self) -> str:
        """
        Retrieve the JIRA 48×48 avatar URL, strip everything **before** the first
        ``?`` and return only the query string.  If the avatar cannot be found
        the function returns the built‑in default ``avatarId=10122``.
        """
        try:
            raw_json = await self._jira_client.get(self.__jira_api_path)
            avatar_url = self._extract_jira_avatar(raw_json)

            if not avatar_url:
                # No avatar – fall back to the known default
                return "avatarId=10122"

            # Extract the query‑string part only
            return self._strip_query(avatar_url)

        except Exception as exc:      # catch *any* unexpected problem
            # Log the exception for observability; still return the default
            import logging

            logging.getLogger(__name__).warning(
                f"Error fetching JIRA avatar for {self.username}: {exc}"
            )
            return "avatarId=10122"

    async def fetchC_profpic(self) -> str:
        """
        Retrieve the Confluence ``profilePicture.path`` and apply the custom
        normalisation rules.  If the picture cannot be found the function
        returns the literal string ``default``.
        """
        try:
            raw_json = await self._conf_client.get(self.__conf_api_path)
            raw_path = self._extract_conf_path(raw_json)

            if not raw_path:
                # No picture → our defined default
                return "default"

            return self._normalize_conf_path(raw_path)

        except Exception as exc:
            # Log unexpected errors, but always give a deterministic fallback
            import logging

            logging.getLogger(__name__).warning(
                f"Error fetching Confluence picture for {self.username}: {exc}"
            )
            return "default"



{
  "app": "jira",
  "group_name": "Jira Guided User",
  "user_owners": [
    {
      "username": "dmoody",
      "email": "d.moody@samsung.com",
      "profilePictureId": "ownerId=dmoody&avatarId=12104"
    },
    {
      "username": "icastillo2",
      "email": "i.castillo2@samsung.com",
      "profilePictureId": "ownerId=icastillo2&avatarId=13121"
    },
    {
      "username": "jlevy",
      "email": "jon.levy@samsung.com",
      "profilePictureId": "avatarId=10349"
    },
    {
      "username": "kkashmiry0641",
      "email": "k.kashmiry@samsung.com",
      "profilePictureId": "ownerId=kkashmiry0641&avatarId=17208"
    },
    {
      "username": "spandeti2572",
      "email": "s.pandeti@samsung.com",
      "profilePictureId": "ownerId=spandeti2572&avatarId=12802"
    }
  ],
  "group_owners": [
    "jira-administrators"
  ]
}
