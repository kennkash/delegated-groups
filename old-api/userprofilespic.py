# userprofilespic.py
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
    from urllib.parse import parse_qs

class ProfilePicFetcher:
    ...
    @staticmethod
    def normalize_jira_profile_picture_id(jira_user_payload: Dict[str, Any]) -> str:
        """
        Given a Jira user payload (from /rest/api/2/user?username=...),
        return the normalized profilePictureId query string, e.g.:

          "ownerId=janedoe1&avatarId=12104"

        If missing, return "avatarId=10122".
        """
        avatar_url = (jira_user_payload.get("avatarUrls") or {}).get("48x48")
        if not avatar_url:
            return "avatarId=10122"

        # reuse the same rule as fetchJ_profpic: take everything after '?'
        qs = ProfilePicFetcher._strip_query(avatar_url)
        return qs or "avatarId=10122"

    @staticmethod
    def jira_avatar_parts_from_profile_picture_id(profile_picture_id: str) -> Dict[str, str]:
        """
        Parse the query-string style profilePictureId into:
          ownerId, avatarId, profilePictureId

        Ensures the same defaults you use today:
          ownerId -> "undefined" if missing
          avatarId -> "10122" if missing
        """
        owner_id = "undefined"
        avatar_id = "10122"

        try:
            parsed = parse_qs(profile_picture_id or "", keep_blank_values=True)
            if parsed.get("ownerId"):
                owner_id = parsed["ownerId"][0] or "undefined"
            if parsed.get("avatarId"):
                avatar_id = parsed["avatarId"][0] or "10122"
        except Exception:
            pass

        return {
            "ownerId": owner_id,
            "avatarId": avatar_id,
            "profilePictureId": f"ownerId={owner_id}&avatarId={avatar_id}",
        }
    
    
    
    
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
    
    @staticmethod
    def normalize_conf_profile_picture_id(conf_user_payload: Dict[str, Any]) -> str:
        """
        Given the Confluence user payload (from /rest/api/user?username=...),
        return the normalized profilePictureId using the same business rules.
        """
        raw_path = conf_user_payload.get("profilePicture", {}).get("path")
        if not raw_path:
            return "default"
        return ProfilePicFetcher._normalize_conf_path(raw_path)

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
