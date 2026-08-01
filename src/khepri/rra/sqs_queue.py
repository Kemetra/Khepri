from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from khepri.rra.worker import ReportJobMessage

MAX_VISIBILITY_TIMEOUT_SECONDS = 12 * 60 * 60


class QueueMessageRejected(ValueError):
    pass


class SqsClient(Protocol):
    def send_message(self, **request: object) -> dict[str, object]: ...

    def receive_message(self, **request: object) -> dict[str, object]: ...

    def change_message_visibility(self, **request: object) -> dict[str, object]: ...

    def delete_message(self, **request: object) -> dict[str, object]: ...


@dataclass(frozen=True, slots=True)
class QueueDelivery:
    message: ReportJobMessage
    receipt_handle: str


class SqsReportPublisher:
    """Publish opaque report identifiers to one source queue."""

    def __init__(self, *, client: SqsClient, queue_url: str) -> None:
        self._client = client
        self._queue_url = _required_text(queue_url)

    def publish(self, message: ReportJobMessage) -> str:
        return _send(self._client, self._queue_url, message)


class SqsReportQueue:
    def __init__(
        self,
        *,
        client: SqsClient,
        queue_url: str,
        dead_letter_queue_url: str,
        visibility_timeout_seconds: int,
    ) -> None:
        self._client = client
        self._queue_url = _required_text(queue_url)
        self._publisher = SqsReportPublisher(client=client, queue_url=self._queue_url)
        self._dead_letter_queue_url = _distinct_destination(
            _required_text(dead_letter_queue_url),
            self._queue_url,
        )
        self._visibility_timeout = _visibility_timeout(visibility_timeout_seconds)

    def publish(self, message: ReportJobMessage) -> str:
        return self._publisher.publish(message)

    def dead_letter(self, delivery: QueueDelivery) -> str:
        """Route an exhausted delivery to the dead-letter queue and drop the source."""
        message_id = _send(self._client, self._dead_letter_queue_url, delivery.message)
        self._client.delete_message(**self._routing(delivery))
        return message_id

    def receive(self) -> QueueDelivery | None:
        response = self._client.receive_message(
            QueueUrl=self._queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
            VisibilityTimeout=self._visibility_timeout,
        )
        message = _single_message(response)
        return None if message is None else _delivery(message)

    def heartbeat(self, delivery: QueueDelivery) -> None:
        self._client.change_message_visibility(
            **self._routing(delivery),
            VisibilityTimeout=self._visibility_timeout,
        )

    def acknowledge(self, delivery: QueueDelivery) -> None:
        self._client.delete_message(**self._routing(delivery))

    def _routing(self, delivery: QueueDelivery) -> dict[str, object]:
        return {
            "QueueUrl": self._queue_url,
            "ReceiptHandle": delivery.receipt_handle,
        }



def _send(client: SqsClient, queue_url: str, message: ReportJobMessage) -> str:
    response = client.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(
            {"job_id": _required_text(message.job_id)},
            sort_keys=True,
            separators=(",", ":"),
        ),
    )
    return _message_id(response)


def _single_message(response: dict[str, object]) -> dict[str, object] | None:
    messages = _message_list(response.get("Messages"))
    if not messages:
        return None
    if len(messages) != 1:
        raise QueueMessageRejected("Queue response has an invalid message set.")
    return _message_entry(messages[0])


def _message_list(value: object) -> list[object]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise QueueMessageRejected("Queue response has an invalid message set.")
    return value


def _message_entry(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise QueueMessageRejected("Queue response has an invalid message.")
    return value


def _delivery(message: dict[str, object]) -> QueueDelivery:
    return QueueDelivery(
        message=ReportJobMessage(job_id=_job_id(message.get("Body"))),
        receipt_handle=_required_text(message.get("ReceiptHandle")),
    )


def _job_id(body: object) -> str:
    document = _document(_decode(_required_text(body)))
    if set(document) != {"job_id"}:
        raise QueueMessageRejected("Queue message has an invalid envelope.")
    return _required_text(document["job_id"])


def _document(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise QueueMessageRejected("Queue message has an invalid envelope.")
    return value


def _decode(body: str) -> object:
    try:
        return json.loads(body)
    except (TypeError, ValueError) as error:
        raise QueueMessageRejected("Queue message is not valid JSON.") from error


def _message_id(response: dict[str, object]) -> str:
    return _required_text(response.get("MessageId"))


def _required_text(value: object) -> str:
    if not isinstance(value, str):
        raise QueueMessageRejected("Required opaque queue metadata is unavailable.")
    if not value.strip():
        raise QueueMessageRejected("Required opaque queue metadata is unavailable.")
    return value


def _distinct_destination(dead_letter_queue_url: str, queue_url: str) -> str:
    if dead_letter_queue_url == queue_url:
        raise ValueError("dead_letter_queue_url must differ from queue_url.")
    return dead_letter_queue_url


def _visibility_timeout(value: int) -> int:
    if not 0 < value <= MAX_VISIBILITY_TIMEOUT_SECONDS:
        raise ValueError("visibility_timeout_seconds is outside SQS bounds.")
    return value
