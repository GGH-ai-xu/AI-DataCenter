from __future__ import annotations

from app.services.runtime_provider import RuntimeTarget


class SavedHostService:
    def __init__(self, identity_store, credential_store):
        self.identity_store = identity_store
        self.credential_store = credential_store

    async def list_hosts(self, actor: dict, scope: str = "mine") -> list[dict]:
        owner_id = None if actor["role"] == "admin" and scope == "all" else actor["id"]
        records = await self.identity_store.list_saved_hosts(owner_user_id=owner_id)
        return [self._decorate_host_record(record) for record in records]

    async def upsert_host(
        self,
        owner: dict,
        target: RuntimeTarget,
        credential_id: str | None,
    ) -> dict:
        return await self.identity_store.upsert_saved_host(
            owner_user_id=owner["id"],
            label=target.label,
            provider_type=target.provider_type,
            host=target.host,
            port=target.port,
            username=target.username,
            auth_type=target.auth_type,
            sudo_enabled=bool(target.sudo_enabled),
            host_fingerprint=target.host_fingerprint,
            agent_url=target.agent_url,
            credential_ref=credential_id,
        )

    async def resolve_for_import(
        self,
        actor: dict,
        host_id: int,
    ) -> tuple[RuntimeTarget, dict, dict]:
        record = await self.identity_store.get_saved_host(host_id)
        if not record:
            raise ValueError("指定主机不存在")
        if actor["role"] != "admin" and record["owner_user_id"] != actor["id"]:
            raise PermissionError("无权访问该主机记录")
        credentials = {}
        if record.get("credential_ref"):
            credentials = self.credential_store.read(record["credential_ref"])
            if not credentials:
                raise ValueError("已保存 SSH 凭据不存在，请切换到“连接来源”重新录入密码或私钥")
        owner = await self.identity_store.get_user_by_id(record["owner_user_id"])
        return _build_target(record), credentials, owner

    async def delete_host(self, actor: dict, host_id: int) -> None:
        record = await self.identity_store.get_saved_host(host_id)
        if not record:
            raise ValueError("指定主机不存在")
        if actor["role"] != "admin" and record["owner_user_id"] != actor["id"]:
            raise PermissionError("无权删除该主机记录")
        if record.get("credential_ref"):
            self.credential_store.delete(record["credential_ref"])
        await self.identity_store.delete_saved_host(host_id)

    def _decorate_host_record(self, record: dict) -> dict:
        credential_status, credential_error = self._credential_state(record)
        return {
            **record,
            "has_credentials": credential_status != "missing",
            "credential_status": credential_status,
            "credential_error": credential_error,
        }

    def _credential_state(self, record: dict) -> tuple[str, str]:
        credential_ref = str(record.get("credential_ref") or "").strip()
        if not credential_ref:
            return "missing", ""
        if not self.credential_store.masked_snapshot(credential_ref):
            return "missing", ""
        try:
            self.credential_store.read(credential_ref)
        except ValueError as exc:
            return "unreadable", str(exc)
        return "ok", ""


def _build_target(record: dict) -> RuntimeTarget:
    return RuntimeTarget(
        provider_type=record["provider_type"],
        label=record["label"],
        agent_url=record.get("agent_url"),
        host=record.get("host"),
        port=record.get("port"),
        username=record.get("username"),
        auth_type=record.get("auth_type"),
        sudo_enabled=bool(record.get("sudo_enabled")),
        host_fingerprint=record.get("host_fingerprint"),
        credential_id=record.get("credential_ref"),
    )
