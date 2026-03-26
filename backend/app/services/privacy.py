"""隐私脱敏服务 - 对外输出与 LLM 上下文统一脱敏。"""

from __future__ import annotations

import hashlib
import re
from typing import Iterable


PATH_PLACEHOLDER = "[path]"


class PrivacyService:
    """对用户名、命令与路径做稳定脱敏，避免泄露个人与主机信息。"""

    _PATH_PATTERN = re.compile(
        r"(?<!\w)(?:"
        r"[A-Za-z]:\\[^\s\"']+"
        r"|\\\\[^\s\"']+"
        r"|/(?:[^/\s\"']+/)+[^/\s\"']*"
        r"|~[\\/][^\s\"']+"
        r"|\.[\\/][^\s\"']+"
        r")"
    )

    def mask_username(self, username: str | None) -> str:
        normalized = (username or "").strip()
        if not normalized or normalized.lower() == "unknown":
            return "unknown"
        digest = hashlib.blake2s(
            normalized.encode("utf-8", errors="ignore"),
            digest_size=3,
        ).hexdigest()
        return f"user-{digest}"

    def resolve_username(
        self,
        value: str | None,
        candidates: Iterable[str] | None = None,
    ) -> str:
        normalized = (value or "").strip()
        if not normalized:
            return normalized

        alias_map: dict[str, str] = {}
        for candidate in candidates or []:
            raw = (candidate or "").strip()
            if not raw:
                continue
            alias_map[raw] = raw
            alias_map[self.mask_username(raw)] = raw

        return alias_map.get(normalized, normalized)

    def mask_path(self, path: str | None) -> str:
        return PATH_PLACEHOLDER if path else ""

    def mask_text(
        self,
        text: str | None,
        known_usernames: Iterable[str] | None = None,
    ) -> str | None:
        if text is None:
            return None

        masked = self._PATH_PATTERN.sub(PATH_PLACEHOLDER, str(text))
        usernames = sorted(
            {
                (username or "").strip()
                for username in (known_usernames or [])
                if (username or "").strip()
            },
            key=len,
            reverse=True,
        )
        for username in usernames:
            masked = masked.replace(username, self.mask_username(username))
        return masked

    def mask_command(self, command: str | None) -> str:
        masked = self.mask_text(command) or ""
        masked = re.sub(r"\s+", " ", masked).strip()
        if len(masked) > 160:
            return masked[:157].rstrip() + "..."
        return masked

    def sanitize_process(self, process: dict) -> dict:
        item = dict(process or {})
        item["username"] = self.mask_username(item.get("username"))
        if "command" in item:
            item["command"] = self.mask_command(item.get("command"))
        return item

    def sanitize_processes(self, processes: list[dict] | None) -> list[dict]:
        return [self.sanitize_process(proc) for proc in (processes or [])]

    def sanitize_timeline_entry(self, entry: dict) -> dict:
        item = dict(entry or {})
        item["username"] = self.mask_username(item.get("username"))
        if "command" in item:
            item["command"] = self.mask_command(item.get("command"))
        return item

    def sanitize_timeline(self, timeline: list[dict] | None) -> list[dict]:
        return [self.sanitize_timeline_entry(item) for item in (timeline or [])]

    def sanitize_training_entry(self, entry: dict) -> dict:
        item = dict(entry or {})
        item["username"] = self.mask_username(item.get("username"))
        item["command"] = self.mask_command(item.get("command"))
        item["working_dir"] = self.mask_path(item.get("working_dir"))
        item["log_file"] = self.mask_path(item.get("log_file"))
        return item

    def sanitize_training_logs(self, logs: list[dict] | None) -> list[dict]:
        return [self.sanitize_training_entry(item) for item in (logs or [])]

    def sanitize_user_stat(self, user: dict) -> dict:
        item = dict(user or {})
        item["username"] = self.mask_username(item.get("username"))
        item["processes"] = self.sanitize_processes(item.get("processes") or [])
        return item

    def sanitize_user_stats(self, users: list[dict] | None) -> list[dict]:
        return [self.sanitize_user_stat(item) for item in (users or [])]

    def sanitize_governance_rule(self, rule: dict | None) -> dict | None:
        if rule is None:
            return None
        item = dict(rule)
        raw_username = item.get("username")
        item["username"] = self.mask_username(raw_username)
        item["note"] = self.mask_text(
            item.get("note") or "",
            known_usernames=[raw_username] if raw_username else [],
        ) or ""
        return item

    def sanitize_governance_report(self, report: dict | None) -> dict:
        payload = dict(report or {})
        users = payload.get("users") or []
        yield_candidates = payload.get("yield_candidates") or []
        known_usernames = {
            (user.get("username") or "").strip()
            for user in users
            if (user.get("username") or "").strip()
        }
        known_usernames.update(
            {
                (item.get("username") or "").strip()
                for item in yield_candidates
                if (item.get("username") or "").strip()
            }
        )

        overview = dict(payload.get("overview") or {})
        dominant_user = overview.get("dominant_user")
        overview["dominant_user"] = self.mask_username(dominant_user) if dominant_user else None
        overview["summary"] = self.mask_text(
            overview.get("summary"),
            known_usernames=known_usernames,
        )

        sanitized_users = []
        for user in users:
            item = dict(user)
            item["username"] = self.mask_username(item.get("username"))
            item["recommended_action"] = self.mask_text(
                item.get("recommended_action"),
                known_usernames=known_usernames,
            )
            item["violations"] = [
                self.mask_text(text, known_usernames=known_usernames) or ""
                for text in (item.get("violations") or [])
            ]
            item["governance_rule"] = self.sanitize_governance_rule(
                item.get("governance_rule")
            )
            sanitized_users.append(item)

        sanitized_candidates = []
        for candidate in yield_candidates:
            item = dict(candidate)
            item["username"] = self.mask_username(item.get("username"))
            item["command"] = self.mask_command(item.get("command"))
            item["yield_reason"] = self.mask_text(
                item.get("yield_reason"),
                known_usernames=known_usernames,
            )
            sanitized_candidates.append(item)

        recommendations = [
            self.mask_text(item, known_usernames=known_usernames) or ""
            for item in (payload.get("recommendations") or [])
        ]

        return {
            "overview": overview,
            "users": sanitized_users,
            "yield_candidates": sanitized_candidates,
            "recommendations": recommendations,
        }

    def sanitize_schedule_history(self, history: dict | None) -> dict:
        payload = dict(history or {})
        logs = []
        for item in payload.get("logs") or []:
            row = dict(item)
            row["reason"] = self.mask_text(row.get("reason")) or ""
            logs.append(row)
        payload["logs"] = logs
        return payload
