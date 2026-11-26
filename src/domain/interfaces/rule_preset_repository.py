from typing import Protocol, List, Optional
from src.domain.models.rule_preset import RulePreset


class RulePresetRepositoryProtocol(Protocol):
    def get_by_id(self, preset_id: int) -> Optional[RulePreset]:
        ...

    def get_by_name(self, name: str) -> Optional[RulePreset]:
        ...

    def list_all(self) -> List[RulePreset]:
        ...

    def save(self, preset: RulePreset) -> RulePreset:
        ...

    def delete(self, preset_id: int) -> bool:
        ...
