"""Multi-turn dialogue state: current intent, pending slots, slot values, turn history."""
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List


@dataclass
class DialogueContext:
    session_id: str
    current_intent: str = ""
    pending_slots: List[str] = field(default_factory=list)
    slots: Dict[str, Any] = field(default_factory=dict)
    turn_history: List[dict] = field(default_factory=list)
    turn_count: int = 0
    unanswered_count: int = 0

    def add_turn(self, user: str, intent: str, rule_id: str, answered: bool):
        self.turn_count += 1
        if not answered:
            self.unanswered_count += 1
        self.turn_history.append({"turn": self.turn_count, "user": user[:200], "intent": intent, "rule_id": rule_id, "answered": answered})
        self.turn_history = self.turn_history[-12:]

    def ask_for(self, intent: str, slot: str):
        self.current_intent = intent
        if slot not in self.pending_slots:
            self.pending_slots.append(slot)

    def fill(self, slot: str, value):
        self.slots[slot] = value
        if slot in self.pending_slots:
            self.pending_slots.remove(slot)

    def clear_pending(self):
        self.pending_slots = []

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "DialogueContext":
        d = dict(d or {})
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})
