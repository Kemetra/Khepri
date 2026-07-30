from __future__ import annotations

import pytest

from khepri.rra.sqs_queue import QueueMessageRejected, SqsReportQueue
from khepri.rra.worker import ReportJobMessage

QUEUE_URL = "https://sqs.me-central-1.amazonaws.com/123/report-jobs"
DEAD_LETTER_URL = "https://sqs.me-central-1.amazonaws.com/123/report-jobs-dead-letter"


class SqsClientStub:
    def __init__(self, responses: list[dict[str, object]] | None = None) -> None:
        self.responses = responses or []
        self.sent: list[dict[str, object]] = []
        self.received: list[dict[str, object]] = []
        self.visibility_changes: list[dict[str, object]] = []
        self.deleted: list[dict[str, object]] = []

    def send_message(self, **request: object) -> dict[str, object]:
        self.sent.append(request)
        return {"MessageId": "msg_alpha"}

    def receive_message(self, **request: object) -> dict[str, object]:
        self.received.append(request)
        return self.responses.pop(0) if self.responses else {}

    def change_message_visibility(self, **request: object) -> dict[str, object]:
        self.visibility_changes.append(request)
        return {}

    def delete_message(self, **request: object) -> dict[str, object]:
        self.deleted.append(request)
        return {}


def queue(client: SqsClientStub) -> SqsReportQueue:
    return SqsReportQueue(
        client=client,
        queue_url=QUEUE_URL,
        dead_letter_queue_url=DEAD_LETTER_URL,
        visibility_timeout_seconds=120,
    )


def one_delivery() -> SqsClientStub:
    return SqsClientStub(
        [
            {
                "Messages": [
                    {
                        "Body": '{"job_id":"job_alpha"}',
                        "ReceiptHandle": "receipt_alpha",
                    }
                ]
            }
        ]
    )


def test_publish_sends_only_the_opaque_job_identifier() -> None:
    client = SqsClientStub()

    message_id = queue(client).publish(ReportJobMessage(job_id="job_alpha"))

    assert message_id == "msg_alpha"
    assert client.sent == [
        {
            "QueueUrl": QUEUE_URL,
            "MessageBody": '{"job_id":"job_alpha"}',
        }
    ]


def test_receive_is_bounded_and_delivery_can_be_renewed_then_acknowledged() -> None:
    client = one_delivery()
    report_queue = queue(client)

    delivery = report_queue.receive()

    assert delivery is not None
    assert delivery.message == ReportJobMessage(job_id="job_alpha")
    assert client.received == [
        {
            "QueueUrl": QUEUE_URL,
            "MaxNumberOfMessages": 1,
            "WaitTimeSeconds": 20,
            "VisibilityTimeout": 120,
        }
    ]

    report_queue.heartbeat(delivery)
    report_queue.acknowledge(delivery)

    routing = {
        "QueueUrl": QUEUE_URL,
        "ReceiptHandle": "receipt_alpha",
    }
    assert client.visibility_changes == [{**routing, "VisibilityTimeout": 120}]
    assert client.deleted == [routing]


@pytest.mark.parametrize("response", [{}, {"Messages": []}])
def test_empty_poll_returns_no_delivery(response: dict[str, object]) -> None:
    assert queue(SqsClientStub([response])).receive() is None


@pytest.mark.parametrize(
    "message",
    [
        {"Body": "not-json", "ReceiptHandle": "receipt_alpha"},
        {"Body": '{"job_id":""}', "ReceiptHandle": "receipt_alpha"},
        {
            "Body": '{"job_id":"job_alpha","filename":"customer.csv"}',
            "ReceiptHandle": "receipt_alpha",
        },
        {"Body": '{"job_id":"job_alpha"}'},
    ],
)
def test_receive_rejects_malformed_or_content_bearing_messages(
    message: dict[str, str],
) -> None:
    report_queue = queue(SqsClientStub([{"Messages": [message]}]))

    with pytest.raises(QueueMessageRejected) as rejected:
        report_queue.receive()

    assert "customer.csv" not in str(rejected.value)


@pytest.mark.parametrize("visibility_timeout_seconds", [0, 43_201])
def test_visibility_timeout_must_stay_within_sqs_bounds(
    visibility_timeout_seconds: int,
) -> None:
    with pytest.raises(ValueError, match="visibility"):
        SqsReportQueue(
            client=SqsClientStub(),
            queue_url=QUEUE_URL,
            dead_letter_queue_url=DEAD_LETTER_URL,
            visibility_timeout_seconds=visibility_timeout_seconds,
        )


def test_dead_letter_sends_only_the_opaque_identifier_then_drops_the_source() -> None:
    client = one_delivery()
    report_queue = queue(client)
    delivery = report_queue.receive()
    assert delivery is not None

    message_id = report_queue.dead_letter(delivery)

    assert message_id == "msg_alpha"
    assert client.sent == [
        {
            "QueueUrl": DEAD_LETTER_URL,
            "MessageBody": '{"job_id":"job_alpha"}',
        }
    ]
    assert client.deleted == [
        {
            "QueueUrl": QUEUE_URL,
            "ReceiptHandle": "receipt_alpha",
        }
    ]


def test_dead_letter_destination_must_be_a_distinct_opaque_queue() -> None:
    with pytest.raises(QueueMessageRejected):
        SqsReportQueue(
            client=SqsClientStub(),
            queue_url=QUEUE_URL,
            dead_letter_queue_url="   ",
            visibility_timeout_seconds=120,
        )
    with pytest.raises(ValueError, match="dead_letter_queue_url"):
        SqsReportQueue(
            client=SqsClientStub(),
            queue_url=QUEUE_URL,
            dead_letter_queue_url=QUEUE_URL,
            visibility_timeout_seconds=120,
        )
