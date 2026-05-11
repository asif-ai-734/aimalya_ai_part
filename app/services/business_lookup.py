from collections.abc import Iterable
from typing import Any

from app.db.business_store import get_user_businesses


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


def _business_name_candidates(business: dict) -> list[str]:
    place_payload = business.get("place_payload") or {}
    raw_input = business.get("raw_input") or {}
    raw_business = raw_input.get("business") or {}

    return _text_values(
        business.get("business_name"),
        place_payload.get("name"),
        raw_business.get("name"),
    )


def _business_address_candidates(business: dict) -> list[str]:
    place_payload = business.get("place_payload") or {}
    raw_input = business.get("raw_input") or {}
    raw_location = raw_input.get("location") or {}

    return _text_values(
        business.get("business_address"),
        business.get("input_address"),
        place_payload.get("formatted_address"),
        raw_location.get("address_or_city"),
    )


def business_matches(
    business: dict,
    *,
    business_name: str,
    address: str | None = None,
) -> bool:
    return _matches_text(
        business_name,
        _business_name_candidates(business),
    ) and _matches_address(
        address,
        _business_address_candidates(business),
    )


async def find_user_business(
    *,
    user_id: str,
    business_name: str,
    address: str | None = None,
) -> dict | None:
    businesses = await get_user_businesses(user_id)

    for business in businesses:
        if business_matches(
            business,
            business_name=business_name,
            address=address,
        ):
            return business

    return None
