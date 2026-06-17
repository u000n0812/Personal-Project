"""설정(config.yaml) 로딩 유틸리티."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# 프로젝트 루트 (이 파일 기준 src/commodity_quant/config.py -> 루트는 3단계 위)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


@dataclass
class Config:
    """config.yaml 내용을 담는 얇은 래퍼.

    값 접근은 ``cfg["data"]["source"]`` 또는 헬퍼 프로퍼티로 한다.
    """

    raw: dict[str, Any] = field(default_factory=dict)

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    # --- 자주 쓰는 접근자 ---
    @property
    def symbols(self) -> list[str]:
        """모든 자산군의 심볼을 평탄화하여 반환."""
        out: list[str] = []
        for group in self.raw.get("assets", {}).values():
            out.extend(group.keys())
        return out

    @property
    def symbol_names(self) -> dict[str, str]:
        """심볼 -> 한글명 매핑."""
        out: dict[str, str] = {}
        for group in self.raw.get("assets", {}).values():
            out.update(group)
        return out

    def group_of(self, symbol: str) -> str | None:
        """심볼이 속한 자산군 이름을 반환."""
        for group_name, group in self.raw.get("assets", {}).items():
            if symbol in group:
                return group_name
        return None


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> Config:
    """YAML 설정 파일을 읽어 :class:`Config` 로 반환한다."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return Config(raw=raw)
