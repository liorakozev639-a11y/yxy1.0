from datetime import datetime, timedelta, timezone
import unittest

from delivery_module import (
    DeliveryError,
    Plan,
    PlanItem,
    WebDelivery,
    WebDeliveryService,
    build_web_payload,
)


class FakeDeliveryRepository:
    """Test double only; production persistence uses PostgreSQLDeliveryRepository."""

    def __init__(self) -> None:
        self.records: dict[tuple[str, str, str], WebDelivery] = {}

    def save_or_get_web(
        self,
        *,
        delivery_id: str,
        session_id: str,
        plan_id: str,
        payload: dict,
        now: datetime,
    ) -> WebDelivery:
        key = (session_id, plan_id, "web")
        if key not in self.records:
            self.records[key] = WebDelivery(
                id=delivery_id,
                session_id=session_id,
                plan_id=plan_id,
                channel="web",
                status="ready",
                payload=payload,
                created_at=now,
            )
        return self.records[key]


class DeliveryModuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tz = timezone.utc
        self.start = datetime(2026, 8, 8, 10, 0, tzinfo=self.tz)
        self.items = (
            PlanItem(
                id="item_002",
                title="阅读 30 分钟",
                category="自我成长",
                start_at=self.start + timedelta(minutes=60),
                end_at=self.start + timedelta(minutes=90),
                status="pending",
            ),
            PlanItem(
                id="item_001",
                title="去公园散步",
                category="活力充电",
                start_at=self.start,
                end_at=self.start + timedelta(minutes=40),
                status="completed",
            ),
        )
        self.plan = Plan(
            id="plan_001",
            session_id="sess_001",
            title="周六半日安排",
            status="confirmed",
            version=2,
            items=self.items,
        )

    def test_build_web_payload_sorts_items_for_timeline(self) -> None:
        payload = build_web_payload("sess_001", self.plan)

        self.assertEqual(payload["channel"], "web")
        self.assertEqual(
            [item["id"] for item in payload["items"]],
            ["item_001", "item_002"],
        )
        self.assertEqual(payload["version"], 2)
        self.assertEqual(payload["items"][0]["status"], "completed")

    def test_delivery_rejects_session_mismatch(self) -> None:
        with self.assertRaisesRegex(DeliveryError, "不属于当前会话"):
            build_web_payload("sess_other", self.plan)

    def test_delivery_rejects_overlapping_plan_items(self) -> None:
        overlap = PlanItem(
            id="item_003",
            title="冲突任务",
            category="松弛疗愈",
            start_at=self.start + timedelta(minutes=20),
            end_at=self.start + timedelta(minutes=50),
        )
        plan = Plan(
            id=self.plan.id,
            session_id=self.plan.session_id,
            title=self.plan.title,
            status=self.plan.status,
            version=self.plan.version,
            items=(*self.plan.items, overlap),
        )

        with self.assertRaisesRegex(DeliveryError, "时间冲突"):
            build_web_payload("sess_001", plan)

    def test_service_returns_ready_web_delivery(self) -> None:
        repository = FakeDeliveryRepository()
        service = WebDeliveryService(repository)

        delivery = service.deliver(
            session_id="sess_001",
            plan=self.plan,
            now=self.start,
        )

        self.assertEqual(delivery.channel, "web")
        self.assertEqual(delivery.status, "ready")
        self.assertEqual(delivery.payload["plan_id"], "plan_001")

    def test_same_plan_delivery_is_idempotent(self) -> None:
        repository = FakeDeliveryRepository()
        service = WebDeliveryService(repository)

        first = service.deliver("sess_001", self.plan, self.start)
        second = service.deliver(
            "sess_001",
            self.plan,
            self.start + timedelta(minutes=1),
        )

        self.assertEqual(first.id, second.id)
        self.assertEqual(len(repository.records), 1)


if __name__ == "__main__":
    unittest.main()
