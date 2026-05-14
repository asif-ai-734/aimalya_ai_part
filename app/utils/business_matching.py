from collections.abc import Iterable
from typing import Any


def _text_values(*values: Any) -> list[str]:
    return [str(value).strip() for value in values if str(value or "").strip()]


def _normalized(value: str) -> str:
    normalized = "".join(
        character if character.isalnum() else " "
        for character in value.casefold()
    )
    return " ".join(normalized.split())


def _compact(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _matches_text(requested: str, candidates: Iterable[str]) -> bool:
    requested_normalized = _normalized(requested)
    requested_compact = _compact(requested)

    if not requested_normalized:
        return False

    for candidate in candidates:
        candidate_normalized = _normalized(candidate)
        candidate_compact = _compact(candidate)

        if requested_normalized == candidate_normalized:
            return True

        if requested_compact and requested_compact == candidate_compact:
            return True

    return False


def _matches_address(requested: str | None, candidates: Iterable[str]) -> bool:
    if not requested or not requested.strip():
        return True

    requested_normalized = _normalized(requested)
    requested_compact = _compact(requested)

    if not requested_normalized:
        return True

    for candidate in candidates:
        candidate_normalized = _normalized(candidate)
        candidate_compact = _compact(candidate)

        if not candidate_normalized:
            continue

        if (
            requested_normalized in candidate_normalized
            or candidate_normalized in requested_normalized
            or requested_compact in candidate_compact
            or candidate_compact in requested_compact
        ):
            return True

    return False


def _current_business_address_candidates(business: dict) -> list[str]:
    return _text_values(
        business.get("business_address"),
        business.get("input_address"),
    )


def business_matches(
    business: dict,
    *,
    business_name: str,
    address: str | None = None,
) -> bool:
    return _matches_text(
        business_name,
        _text_values(business.get("business_name")),
    ) and _matches_address(
        address,
        _current_business_address_candidates(business),
    )
