"""Thin async client for the 3X-UI panel API (Bearer token auth)."""
from urllib.parse import quote

import httpx

GB = 1024 ** 3


class PanelError(Exception):
    """Network/HTTP failure talking to the panel."""


class PanelAPIError(PanelError):
    """The panel answered with success=false."""


class PanelNotFound(PanelError):
    """HTTP 404."""


def _e(email: str) -> str:
    return quote(email, safe="")


class Panel:
    def __init__(self, base_url: str, token: str, verify_ssl: bool = True):
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=20,
            verify=verify_ssl,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs):
        try:
            resp = await self._client.request(method, path.lstrip("/"), **kwargs)
        except httpx.HTTPError as exc:
            raise PanelError(f"connection error: {exc!r}") from exc
        if resp.status_code in (401, 403):
            raise PanelError(f"HTTP {resp.status_code}: unauthorized (check PANEL_TOKEN)")
        if resp.status_code == 404:
            raise PanelNotFound("HTTP 404: not found (check PANEL_URL and its base path)")
        if resp.status_code >= 400:
            raise PanelError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise PanelError(f"non-JSON response (check PANEL_URL): {resp.text[:200]}") from exc
        if not data.get("success"):
            raise PanelAPIError(data.get("msg") or "panel returned success=false")
        return data.get("obj")

    # ---- inbounds ----
    async def inbound_options(self) -> list:
        return await self._request("GET", "/panel/api/inbounds/options") or []

    async def find_inbound_id(self, remark: str) -> int:
        for inbound in await self.inbound_options():
            if inbound.get("remark") == remark:
                return int(inbound["id"])
        raise PanelError(f"no inbound with remark '{remark}'")

    # ---- clients ----
    async def get_client(self, email: str):
        """Client record, or None when the panel says it does not exist."""
        try:
            return await self._request("GET", f"/panel/api/clients/get/{_e(email)}")
        except (PanelAPIError, PanelNotFound):
            # A wrong PANEL_URL still surfaces: the add call that follows fails with 404.
            return None

    async def add_client(self, *, email: str, uuid: str, sub_id: str, total_bytes: int,
                         tg_id: int, comment: str, inbound_id: int) -> None:
        payload = {
            "client": {
                "email": email,
                "id": uuid,
                "subId": sub_id,
                "totalGB": total_bytes,
                "expiryTime": 0,
                "limitIp": 0,
                "limitHwid": 0,
                "tgId": tg_id,
                "comment": comment,
                "enable": True,
            },
            "inboundIds": [inbound_id],
        }
        await self._request("POST", "/panel/api/clients/add", json=payload)

    async def client_traffic(self, email: str) -> dict:
        return await self._request("GET", f"/panel/api/clients/traffic/{_e(email)}") or {}

    async def client_links(self, email: str) -> list:
        return await self._request("GET", f"/panel/api/clients/links/{_e(email)}") or []

    async def reset_traffic(self, email: str) -> None:
        await self._request("POST", f"/panel/api/clients/resetTraffic/{_e(email)}")

    async def bulk_reset_traffic(self, emails: list) -> dict:
        return await self._request("POST", "/panel/api/clients/bulkResetTraffic", json={"emails": emails}) or {}

    async def set_enabled(self, email: str, enabled: bool) -> None:
        path = "/panel/api/clients/bulkEnable" if enabled else "/panel/api/clients/bulkDisable"
        await self._request("POST", path, json={"emails": [email]})

    async def delete_client(self, email: str) -> None:
        await self._request("POST", f"/panel/api/clients/del/{_e(email)}", params={"keepTraffic": 0})

    # ---- settings ----
    async def subscription_base(self) -> str | None:
        """Build the subscription base URL (ending in '/') from the panel's settings."""
        s = await self._request("POST", "/panel/api/setting/all") or {}
        if not s.get("subEnable", False):
            return None
        uri = (s.get("subURI") or "").strip()
        if uri:
            return uri if uri.endswith("/") else uri + "/"
        host = (s.get("subDomain") or "").strip() or httpx.URL(str(self._client.base_url)).host
        port = int(s.get("subPort") or 2096)
        scheme = "https" if (s.get("subCertFile") or s.get("subKeyFile")) else "http"
        path = "/" + (s.get("subPath") or "/sub/").strip("/") + "/"
        default_port = {"https": 443, "http": 80}[scheme]
        netloc = host if port == default_port else f"{host}:{port}"
        return f"{scheme}://{netloc}{path}"
