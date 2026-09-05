"""Append-only, hash-chained JSONL evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4


class EvidenceIntegrityError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


@dataclass(frozen=True)
class EvidenceEvent:
    id: str
    sequence: int
    timestamp: str
    event_type: str
    payload: Mapping[str, Any]
    previous_hash: str | None
    hash: str


class EvidenceStore:
    """A JSONL log whose sequence and hash chain are verified before each append."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)
        self.verify()

    def records(self) -> tuple[EvidenceEvent, ...]:
        events = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(EvidenceEvent(**json.loads(line)))
        return tuple(events)

    @staticmethod
    def _digest(unsigned: Mapping[str, Any]) -> str:
        return sha256(_canonical(unsigned)).hexdigest()

    def append(self, event_type: str, payload: Mapping[str, Any]) -> EvidenceEvent:
        existing = self.verify()
        unsigned = {
            "id": str(uuid4()),
            "sequence": len(existing),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "payload": json.loads(json.dumps(payload, default=str)),
            "previous_hash": existing[-1].hash if existing else None,
        }
        event = EvidenceEvent(**unsigned, hash=self._digest(unsigned))
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(asdict(event), sort_keys=True, ensure_ascii=False) + "\n")
        return event

    def verify(self) -> tuple[EvidenceEvent, ...]:
        events = self.records()
        previous = None
        for sequence, event in enumerate(events):
            unsigned = asdict(event)
            digest = unsigned.pop("hash")
            if event.sequence != sequence or event.previous_hash != previous:
                raise EvidenceIntegrityError("evidence ordering or hash chain is invalid")
            if digest != self._digest(unsigned):
                raise EvidenceIntegrityError("evidence event content was modified")
            previous = event.hash
        return events
