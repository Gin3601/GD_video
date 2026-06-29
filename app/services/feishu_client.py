import time
from typing import Any

import httpx

from app.core.config import settings


class FeishuConfigError(RuntimeError):
    pass


class FeishuAPIError(RuntimeError):
    pass


class FeishuClient:
    base_url = "https://open.feishu.cn/open-apis"

    def __init__(self) -> None:
        self._tenant_access_token: str | None = None
        self._tenant_access_token_expires_at = 0.0

    def _require_config(self) -> None:
        if not settings.feishu_app_id or not settings.feishu_app_secret:
            raise FeishuConfigError("FEISHU_APP_ID and FEISHU_APP_SECRET are required")

    async def get_tenant_access_token(self) -> str:
        self._require_config()
        if self._tenant_access_token and time.time() < self._tenant_access_token_expires_at:
            return self._tenant_access_token

        payload = {
            "app_id": settings.feishu_app_id,
            "app_secret": settings.feishu_app_secret,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/auth/v3/tenant_access_token/internal",
                json=payload,
            )
        data = response.json()
        if response.status_code >= 400 or data.get("code", 0) != 0:
            raise FeishuAPIError(f"Failed to get tenant_access_token: {data}")
        token = data.get("tenant_access_token")
        if not token:
            raise FeishuAPIError("Feishu response did not include tenant_access_token")
        expire_seconds = int(data.get("expire", 7200))
        self._tenant_access_token = token
        self._tenant_access_token_expires_at = time.time() + max(expire_seconds - 300, 60)
        return token

    async def get_bitable_record(
        self,
        *,
        app_token: str,
        table_id: str,
        record_id: str,
    ) -> dict[str, Any]:
        token = await self.get_tenant_access_token()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
                headers=self._headers(token),
            )
        data = response.json()
        if response.status_code >= 400 or data.get("code", 0) != 0:
            raise FeishuAPIError(f"Failed to read bitable record: {data}")
        return data["data"]["record"]

    async def search_bitable_records(
        self,
        *,
        app_token: str,
        table_id: str,
        page_size: int = 100,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        token = await self.get_tenant_access_token()
        params: dict[str, Any] = {}
        if page_token:
            params["page_token"] = page_token

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/bitable/v1/apps/{app_token}/tables/{table_id}/records/search",
                headers=self._headers(token),
                params=params,
                json={"page_size": page_size},
            )
        data = response.json()
        if response.status_code >= 400 or data.get("code", 0) != 0:
            raise FeishuAPIError(f"Failed to search bitable records: {data}")
        return data["data"]

    async def create_bitable_record(
        self,
        *,
        app_token: str,
        table_id: str,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        token = await self.get_tenant_access_token()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/bitable/v1/apps/{app_token}/tables/{table_id}/records",
                headers=self._headers(token),
                json={"fields": fields},
            )
        data = response.json()
        if response.status_code >= 400 or data.get("code", 0) != 0:
            raise FeishuAPIError(f"Failed to create bitable record: {data}")
        return data["data"]["record"]

    async def update_bitable_record(
        self,
        *,
        app_token: str,
        table_id: str,
        record_id: str,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        token = await self.get_tenant_access_token()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.put(
                f"{self.base_url}/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
                headers=self._headers(token),
                json={"fields": fields},
            )
        data = response.json()
        if response.status_code >= 400 or data.get("code", 0) != 0:
            raise FeishuAPIError(f"Failed to update bitable record: {data}")
        return data["data"]["record"]

    def _headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }
