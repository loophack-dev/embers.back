"""Supabase Storage client (REST) using the service role key."""

from __future__ import annotations

from urllib.parse import quote

import httpx


class SupabaseStorage:
    def __init__(
        self, http: httpx.AsyncClient, *, base_url: str, service_role_key: str, bucket: str
    ) -> None:
        self._http = http
        self._base = f"{base_url.rstrip('/')}/storage/v1"
        self._headers = {"Authorization": f"Bearer {service_role_key}", "apikey": service_role_key}
        self._bucket = bucket

    async def upload(self, path: str, content: bytes, mime: str) -> None:
        response = await self._http.post(
            f"{self._base}/object/{self._bucket}/{path}",
            content=content,
            headers={**self._headers, "Content-Type": mime, "x-upsert": "true"},
            timeout=30,
        )
        response.raise_for_status()

    async def signed_url(self, path: str, *, expires_in_s: int, download_name: str) -> str:
        response = await self._http.post(
            f"{self._base}/object/sign/{self._bucket}/{path}",
            json={"expiresIn": expires_in_s},
            headers=self._headers,
            timeout=10,
        )
        response.raise_for_status()
        signed_path: str = response.json()["signedURL"]
        return f"{self._base}{signed_path}&download={quote(download_name)}"
