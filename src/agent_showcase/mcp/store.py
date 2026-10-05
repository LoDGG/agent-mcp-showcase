"""Small, resettable in-memory email fixture store."""

from copy import deepcopy


_FIXTURES = (
    {"id": "msg-newsletter", "sender": "digest@example.test",
     "subject": "Weekly digest", "body": "Synthetic community news.", "labels": ["INBOX"]},
    {"id": "msg-invoice", "sender": "billing@example.test",
     "subject": "September invoice", "body": "Synthetic September invoice for 42 credits.",
     "labels": ["INBOX"]},
)


class FakeEmailStore:
    """Owns local fixture state; create a new instance or call reset for isolation."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._messages = {message["id"]: deepcopy(message) for message in _FIXTURES}

    def search_email(self, query: str = "") -> list[dict]:
        """Case-insensitive substring search over sender, subject, and body."""
        if not isinstance(query, str):
            raise ValueError("query must be a string")
        needle = query.strip().casefold()
        matches = []
        for message in self._messages.values():
            haystack = " ".join(message[key] for key in ("sender", "subject", "body"))
            if needle in haystack.casefold():
                matches.append({key: deepcopy(message[key]) for key in ("id", "sender", "subject", "labels")})
        return matches

    def get_email(self, message_id: str) -> dict:
        if message_id not in self._messages:
            raise ValueError(f"Unknown message ID: {message_id}")
        return deepcopy(self._messages[message_id])

    def apply_label(self, message_id: str, label: str) -> dict:
        if message_id not in self._messages:
            raise ValueError(f"Unknown message ID: {message_id}")
        if not isinstance(label, str) or not label.strip() or label != label.strip():
            raise ValueError("label must be a non-empty string without surrounding whitespace")
        if any(ord(char) < 32 for char in label):
            raise ValueError("label must not contain control characters")
        labels = self._messages[message_id]["labels"]
        added = label not in labels
        if added:
            labels.append(label)
        return {"message_id": message_id, "label": label, "added": added, "labels": labels.copy()}

    def archive_email(self, message_id: str) -> dict:
        self.get_email(message_id)  # Validate before mutation.
        labels = self._messages[message_id]["labels"]
        archived = "INBOX" in labels
        if archived:
            labels.remove("INBOX")
        return {"message_id": message_id, "archived": archived, "labels": labels.copy()}
