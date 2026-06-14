import json

from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.domain.models import StrategyActiveBinding, StrategyVersionRecord, utc_now


DEFAULT_STRATEGY_ID = "deterministic_watchlist_v1"
DEFAULT_STRATEGY_VERSION = "v1"
DEFAULT_STRATEGY_PARAMETERS_JSON = '{"notional": 2000}'


class StrategyVersionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str
    version: str
    parameters_json: str
    status: str
    is_active: bool


class StrategyVersionControlPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_strategy_id: str
    active_version: str
    previous_version: str | None
    versions: list[StrategyVersionPayload]


def get_strategy_version_control(
    session: Session,
    strategy_id: str = DEFAULT_STRATEGY_ID,
) -> StrategyVersionControlPayload:
    binding = _get_or_seed_active_binding(session, strategy_id)
    versions = _strategy_versions(session, strategy_id)
    return StrategyVersionControlPayload(
        active_strategy_id=binding.strategy_id,
        active_version=binding.active_version,
        previous_version=binding.previous_version,
        versions=[
            StrategyVersionPayload(
                strategy_id=version.strategy_id,
                version=version.version,
                parameters_json=version.parameters_json,
                status=version.status,
                is_active=version.version == binding.active_version,
            )
            for version in versions
        ],
    )


def get_active_strategy_version(
    session: Session,
    strategy_id: str = DEFAULT_STRATEGY_ID,
) -> StrategyVersionRecord:
    binding = _get_or_seed_active_binding(session, strategy_id)
    version = _find_strategy_version(session, strategy_id, binding.active_version)
    if version is None:
        version = _seed_strategy_version(session, strategy_id, binding.active_version)
    return version


def register_strategy_version(
    session: Session,
    *,
    strategy_id: str,
    version: str,
    parameters_json: str = "{}",
) -> StrategyVersionPayload:
    normalized_strategy_id = _normalize_non_empty(strategy_id, "strategy_id")
    normalized_version = _normalize_non_empty(version, "version")
    _validate_parameters_json(parameters_json)

    record = _find_strategy_version(session, normalized_strategy_id, normalized_version)
    if record is None:
        record = StrategyVersionRecord(
            strategy_id=normalized_strategy_id,
            version=normalized_version,
            parameters_json=parameters_json,
        )
        session.add(record)
    else:
        record.parameters_json = parameters_json
        record.status = "registered"
    session.commit()

    binding = _get_or_seed_active_binding(session, normalized_strategy_id)
    return StrategyVersionPayload(
        strategy_id=record.strategy_id,
        version=record.version,
        parameters_json=record.parameters_json,
        status=record.status,
        is_active=record.version == binding.active_version,
    )


def activate_strategy_version(
    session: Session,
    *,
    strategy_id: str,
    version: str,
    reason: str,
) -> StrategyVersionControlPayload:
    normalized_strategy_id = _normalize_non_empty(strategy_id, "strategy_id")
    normalized_version = _normalize_non_empty(version, "version")
    version_record = _find_strategy_version(session, normalized_strategy_id, normalized_version)
    if version_record is None:
        raise ValueError(f"Strategy version is not registered: {normalized_strategy_id}@{normalized_version}")
    _validate_executable_strategy_parameters(normalized_strategy_id, version_record.parameters_json)

    binding = _get_or_seed_active_binding(session, normalized_strategy_id)
    if binding.active_version != normalized_version:
        binding.previous_version = binding.active_version
        binding.active_version = normalized_version
    binding.activation_reason = reason.strip()
    binding.updated_at = utc_now()
    session.add(binding)
    session.commit()
    return get_strategy_version_control(session, normalized_strategy_id)


def rollback_strategy_version(
    session: Session,
    *,
    strategy_id: str,
) -> StrategyVersionControlPayload:
    normalized_strategy_id = _normalize_non_empty(strategy_id, "strategy_id")
    binding = _get_or_seed_active_binding(session, normalized_strategy_id)
    if binding.previous_version is None:
        raise ValueError(f"Strategy has no previous version to roll back to: {normalized_strategy_id}")
    if _find_strategy_version(session, normalized_strategy_id, binding.previous_version) is None:
        raise ValueError(f"Previous strategy version is missing: {normalized_strategy_id}@{binding.previous_version}")

    current_version = binding.active_version
    binding.active_version = binding.previous_version
    binding.previous_version = current_version
    binding.activation_reason = "rollback"
    binding.updated_at = utc_now()
    session.add(binding)
    session.commit()
    return get_strategy_version_control(session, normalized_strategy_id)


def _get_or_seed_active_binding(session: Session, strategy_id: str) -> StrategyActiveBinding:
    normalized_strategy_id = _normalize_non_empty(strategy_id, "strategy_id")
    _seed_strategy_version(session, normalized_strategy_id, DEFAULT_STRATEGY_VERSION)
    binding = session.exec(
        select(StrategyActiveBinding).where(StrategyActiveBinding.strategy_id == normalized_strategy_id)
    ).first()
    if binding is not None:
        return binding

    binding = StrategyActiveBinding(
        strategy_id=normalized_strategy_id,
        active_version=DEFAULT_STRATEGY_VERSION,
        activation_reason="default seed",
    )
    session.add(binding)
    session.commit()
    session.refresh(binding)
    return binding


def _seed_strategy_version(session: Session, strategy_id: str, version: str) -> StrategyVersionRecord:
    record = _find_strategy_version(session, strategy_id, version)
    if record is not None:
        return record

    parameters_json = DEFAULT_STRATEGY_PARAMETERS_JSON if version == DEFAULT_STRATEGY_VERSION else "{}"
    record = StrategyVersionRecord(strategy_id=strategy_id, version=version, parameters_json=parameters_json)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def _strategy_versions(session: Session, strategy_id: str) -> list[StrategyVersionRecord]:
    return list(
        session.exec(
            select(StrategyVersionRecord)
            .where(StrategyVersionRecord.strategy_id == strategy_id)
            .order_by(StrategyVersionRecord.version)
        ).all()
    )


def _find_strategy_version(session: Session, strategy_id: str, version: str) -> StrategyVersionRecord | None:
    return session.exec(
        select(StrategyVersionRecord).where(
            StrategyVersionRecord.strategy_id == strategy_id,
            StrategyVersionRecord.version == version,
        )
    ).first()


def _validate_parameters_json(value: str) -> None:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError("parameters_json must be valid JSON") from error
    if not isinstance(parsed, dict):
        raise ValueError("parameters_json must encode a JSON object")


def _validate_executable_strategy_parameters(strategy_id: str, parameters_json: str) -> None:
    if strategy_id != DEFAULT_STRATEGY_ID:
        return
    try:
        parsed = json.loads(parameters_json)
    except json.JSONDecodeError as error:
        raise ValueError("parameters_json must be valid JSON") from error
    if not isinstance(parsed, dict):
        raise ValueError("parameters_json must encode a JSON object")
    raw_notional = parsed.get("notional", json.loads(DEFAULT_STRATEGY_PARAMETERS_JSON)["notional"])
    if not isinstance(raw_notional, int | float) or isinstance(raw_notional, bool):
        raise ValueError("Active strategy notional must be numeric")
    if float(raw_notional) <= 0:
        raise ValueError("Active strategy notional must be positive")


def _normalize_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized
