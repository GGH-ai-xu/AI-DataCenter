import os
import sys
import tempfile
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.data_store import DataStore  # noqa: E402
from app.models.schemas import (  # noqa: E402
    ControlCommandApprovalRequest,
    ControlCommandCreateRequest,
)
from app.services.control_plane.models import ControlCommandRecord  # noqa: E402


class ControlPlaneModelTests(unittest.IsolatedAsyncioTestCase):
    async def test_store_round_trips_command_record_and_sorts_newest_first(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = DataStore(os.path.join(tmpdir, "control.db"))
            await store.init()
            try:
                await store.create_control_command(
                    ControlCommandRecord(
                        command_id="cmd-1",
                        capability_name="tasks.pause",
                        domain="tasks",
                        operator_id="alice",
                        operator_type="manual",
                        workspace_key="user:2",
                        source_page="governance-actions",
                        arguments={"pid": 42},
                        risk_level="control",
                        permission_mode="confirm_required",
                        approval_state="approved",
                        execution_state="succeeded",
                        result_summary="paused",
                        error_message="",
                        related_session_id="",
                    )
                )
                rows = await store.list_control_commands(limit=10)
                row = await store.get_control_command("cmd-1")
            finally:
                await store.close()

        self.assertEqual(rows[0]["command_id"], "cmd-1")
        self.assertEqual(row["arguments"]["pid"], 42)
        self.assertEqual(row["execution_state"], "succeeded")

    def test_command_record_normalizes_json_like_fields(self):
        record = ControlCommandRecord(
            command_id="cmd-2",
            capability_name="scheduler.run_once",
            domain="scheduler",
            operator_id="alice",
            operator_type="manual",
            workspace_key="user:2",
            source_page="governance-policies",
            arguments=[("acknowledge_risk", True)],
            risk_level="control",
            permission_mode="confirm_required",
            approval_state="not_required",
            execution_state="queued",
            result_summary=None,
            error_message=None,
            related_session_id=None,
        )

        self.assertEqual(record.arguments["acknowledge_risk"], True)
        self.assertEqual(record.result_summary, "")
        self.assertEqual(record.error_message, "")
        self.assertEqual(record.related_session_id, "")

    def test_control_command_schema_defaults_match_manual_control_flow(self):
        create_request = ControlCommandCreateRequest(
            capability_name="scheduler.run_once",
            arguments={"acknowledge_risk": True},
        )
        approval_request = ControlCommandApprovalRequest(approved=True)

        self.assertEqual(create_request.source_page, "")
        self.assertEqual(create_request.arguments["acknowledge_risk"], True)
        self.assertEqual(approval_request.comment, "")


if __name__ == "__main__":
    unittest.main()
