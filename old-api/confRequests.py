from sas_auth_wrapper import get_external_api_session
from ..credentials.tokens import AtlassianToken
from ..aiServices.errorHandler import ErrorHandler
import requests
import json
from typing import Dict, Optional, Any
from enum import Enum
from dataclasses import dataclass

class ConfEnv(str, Enum):
    """Logical environments understood by ``ConfAPIClient``."""
    PROD = "prod"
    STAGING = "stg"                      

    @property
    def base_url(self) -> str:
        """Map the enum to its concrete base URL."""
        mapping = {
            ConfEnv.PROD:    "http://confluence.externalapi.smartcloud.samsungaustin.com",
            ConfEnv.STAGING: "http://confluencestg.externalapi.smartcloud.samsungaustin.com",
        }
        return mapping[self]

@dataclass
class ResponseData:
    """Container returned by ConfAPIClient methods."""
    status_code: int
    json: Optional[dict] = None
    text: Optional[str] = None
    ok: bool = False

    @property
    def data(self) -> Any:
        """Prefer JSON, fall back to plain text."""
        return self.json if self.json is not None else self.text

class ConfAPIClient:
    """Handles creation and management of the Confluence instance."""

    _BASE_URL = str

    def __init__(
        self, 
        api_token=None,
        *,
        env: Optional[str | ConfEnv] = None,):
        """Initializes client with token and creates a Confluence instance."""
        
        if env is None:
            # No env supplied → use production
            chosen_env = ConfEnv.PROD
        else:
            # Accept either the raw string or the Enum instance
            if isinstance(env, ConfEnv):
                chosen_env = env
            else:
                try:
                    chosen_env = ConfEnv(env.lower())
                except ValueError as exc:
                    raise ValueError(
                        f"Unsupported env '{env}'. Allowed values: {[e.value for e in ConfEnv]}"
                    ) from exc

        self._BASE_URL = chosen_env.base_url.rstrip("/")
        
        self._api_token = AtlassianToken("confluence").getCreds() if api_token is None else api_token
        self._external_api_session = get_external_api_session()

    def _prepare_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._api_token}"}
    
    def _handle_response(self, r: requests.Response) -> ResponseData:
        """Parse the response and always return a ResponseData, never raise."""
        try:
            json_body = r.json()
        except json.JSONDecodeError:
            json_body = None

        return ResponseData(
            status_code=r.status_code,
            json=json_body,
            text=r.text,
            ok=r.ok,
        )
    

    async def get(self, api_path: str) -> dict:
        """Makes an asynchronous GET request to the specified Confluence API path."""
        header =  self._prepare_headers()
        full_url = f'{self._BASE_URL}/rest/{api_path}'

        try:
            r =  self._external_api_session.get(full_url, headers=header)
            response_json = r.json()
            return response_json
        except requests.RequestException as exc:
            raise ErrorHandler(f"Network error while GET {full_url}: {exc}", exc) from exc
        

    async def post(self, api_path: str, post_body: dict) -> dict:
        """Makes an asynchronous POST request to the specified Confluence API path."""
        header = self._prepare_headers()
        header["Content-Type"] = "application/json"
        full_url = f'{self._BASE_URL}/rest/{api_path}'
        try:
            r =  self._external_api_session.post(full_url, data=json.dumps(post_body), headers=header)
            return self._handle_response(r)
        except requests.RequestException as exc:
            raise ErrorHandler(f"Network error while POST {full_url}: {exc}", exc) from exc
        
    async def put(self, api_path: str) -> dict:
        """Makes an asynchronous PUT request to the specified Confluence API path."""
        header = self._prepare_headers()
        header["Content-Type"] = "application/json"
        full_url = f'{self._BASE_URL}/rest/{api_path}'

        try:
            r =  self._external_api_session.put(full_url, headers=header)
            return self._handle_response(r)
        except requests.RequestException as exc:
            raise ErrorHandler(f"Network error while PUT {full_url}: {exc}", exc) from exc
        
    async def delete(self, api_path: str) -> dict:
        """Makes an asynchronous DELETE request to the specified Confluence API path."""
        header = self._prepare_headers()
        header["Content-Type"] = "application/json"
        full_url = f'{self._BASE_URL}/rest/{api_path}'

        try:
            r =  self._external_api_session.delete(full_url, headers=header)
            return self._handle_response(r)
        except requests.RequestException as exc:
            raise ErrorHandler(f"Network error while DELETE {full_url}: {exc}", exc) from exc
