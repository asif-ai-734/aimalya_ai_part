# import asyncio

# from app.db.business_context_store import (
#     get_latest_business_context,
#     get_latest_business_context_by_name,
#     update_business_context_goals,
# )
# from app.db.place_store import upsert_place_data
# from app.schemas.goals_set_up_py import GoalsSetupRequest
# from app.services.google_places_service import (
#     GooglePlacesError,
#     resolve_place_from_url_or_text,
#     summarize_place,
# )


# class GoalsSetupError(Exception):
#     def __init__(self, message: str, status_code: int = 400):
#         super().__init__(message)
#         self.status_code = status_code


# async def _context_for_goals(payload: GoalsSetupRequest) -> dict:
#     context = await get_latest_business_context_by_name(
#         payload.business_name,
#         user_id=payload.user_id,
#     )
#     if context:
#         return context

#     context = await get_latest_business_context(user_id=payload.user_id)
#     if context:
#         return context

#     raise GoalsSetupError(
#         "Submit POST /businesses/fetch before setting goals.",
#         status_code=404,
#     )


# async def _resolve_competitor_place(competitor_url: str) -> dict:
#     try:
#         competitor = await resolve_place_from_url_or_text(competitor_url)
#         place_id = competitor.get("place_id")
#         if not place_id:
#             raise GoalsSetupError(
#                 "Google Places did not return a place_id.",
#                 status_code=502,
#             )
#         return {
#             "competitor_url": competitor_url,
#             "place_id": place_id,
#             "place": competitor,
#             "error": None,
#         }
#     except (GooglePlacesError, GoalsSetupError) as exc:
#         return {
#             "competitor_url": competitor_url,
#             "place_id": None,
#             "place": None,
#             "error": {
#                 "competitor_url": competitor_url,
#                 "status_code": getattr(exc, "status_code", 400),
#                 "error": str(exc),
#             },
#         }


# async def fetch_and_save_goals_setup(payload: GoalsSetupRequest) -> dict:
#     context = await _context_for_goals(payload)
#     own_place_ids = set(context.get("place_ids", []))
#     competitor_place_ids: list[str] = []
#     competitor_places: list[dict] = []
#     competitor_errors: list[dict] = []

#     resolved_competitors = await asyncio.gather(
#         *(
#             _resolve_competitor_place(competitor_url)
#             for competitor_url in payload.competitors_urls
#         )
#     )

#     for resolved in resolved_competitors:
#         if resolved["error"]:
#             competitor_errors.append(resolved["error"])
#             continue

#         place_id = resolved["place_id"]
#         if place_id in own_place_ids or place_id in competitor_place_ids:
#             continue

#         competitor_place_ids.append(place_id)
#         competitor_places.append(resolved["place"])

#     for place in competitor_places:
#         await upsert_place_data(place)

#     if not competitor_place_ids:
#         error_details = "; ".join(
#             f"{item['competitor_url']}: {item['error']}"
#             for item in competitor_errors
#         )
#         message = "No competitor places could be fetched from competitors_urls."
#         if error_details:
#             message = f"{message} {error_details}"
#         raise GoalsSetupError(
#             message,
#             status_code=400,
#         )

#     updated_context = await update_business_context_goals(
#         context_id=context["id"],
#         competitor_place_ids=competitor_place_ids,
#         report_frequency=payload.report_frequency,
#         goals=payload.goals,
#         goals_input=payload.model_dump(),
#     )
#     if not updated_context:
#         raise GoalsSetupError(
#             "Could not update the saved business context.",
#             status_code=500,
#         )

#     return {
#         "status": "saved",
#         "context_id": updated_context["id"],
#         "business_name": updated_context.get("business_name"),
#         "report_frequency": updated_context.get("report_frequency"),
#         "goals": updated_context.get("goals", []),
#         "competitors": [summarize_place(place) for place in competitor_places],
#         "competitor_errors": competitor_errors,
#     }


import asyncio

from app.db.business_context_store import (
    get_latest_business_context,
    save_business_context,
    update_business_context_goals,
)
from app.db.business_store import get_user_businesses
from app.db.place_store import upsert_place_data
from app.schemas.goals_set_up_py import GoalsSetupRequest
from app.services.google_places_service import (
    GooglePlacesError,
    resolve_place_from_url_or_text,
    summarize_place,
)
from app.services.business_lookup import business_matches


class GoalsSetupError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


async def _business_for_goals(
    *,
    user_id: str | None,
    business_name: str,
    location: str,
) -> tuple[dict, set[str]]:
    if not user_id:
        raise GoalsSetupError(
            "user_id is required to set goals for a specific business location.",
            status_code=400,
        )

    user_businesses = await get_user_businesses(user_id)
    own_businesses = [
        saved_business
        for saved_business in user_businesses
        if business_matches(
            saved_business,
            business_name=business_name,
        )
    ]
    matched_locations = [
        saved_business
        for saved_business in own_businesses
        if business_matches(
            saved_business,
            business_name=business_name,
            address=location,
        )
    ]

    if not matched_locations:
        raise GoalsSetupError(
            (
                "Business not found for this user, business_name, and location. "
                "Submit POST /businesses/fetch first, then use one of the saved "
                "location addresses."
            ),
            status_code=404,
        )

    own_place_ids = {
        saved_business["place_id"]
        for saved_business in own_businesses
        if saved_business.get("place_id")
    }
    return matched_locations[0], own_place_ids


def _location_address(
    saved_business: dict,
    requested_location: str | None,
) -> str | None:
    return (
        saved_business.get("business_address")
        or saved_business.get("input_address")
        or requested_location
    )


def _is_location_scoped_context(context: dict | None, place_id: str) -> bool:
    if not context:
        return False
    return (
        context.get("primary_place_id") == place_id
        and context.get("place_ids") == [place_id]
    )


def _goals_raw_input(base_context: dict | None, goals_input: dict) -> dict:
    current_raw_input = (base_context or {}).get("raw_input", {})
    business_setup = current_raw_input.get("business_setup", current_raw_input)
    return {
        "business_setup": business_setup,
        "goals_setup": goals_input,
    }


async def _save_or_update_goals_context(
    *,
    context: dict | None,
    matched_business: dict,
    user_id: str | None,
    selected_place_id: str,
    competitor_place_ids: list[str],
    goals: list[str],
    goals_input: dict,
) -> dict | None:
    if _is_location_scoped_context(context, selected_place_id):
        return await update_business_context_goals(
            context_id=context["id"],
            competitor_place_ids=competitor_place_ids,
            goals=goals,
            goals_input=goals_input,
        )

    await save_business_context(
        user_id=user_id,
        primary_place_id=selected_place_id,
        place_ids=[selected_place_id],
        competitor_place_ids=competitor_place_ids,
        business_name=matched_business.get("business_name"),
        business_address=_location_address(
            matched_business,
            goals_input.get("location"),
        ),
        business_category=matched_business.get("business_category"),
        report_frequency=context.get("report_frequency") if context else None,
        goals=goals,
        raw_input=_goals_raw_input(context, goals_input),
    )

    return await get_latest_business_context(
        selected_place_id,
        user_id=user_id,
    )


async def _resolve_competitor_place(competitor_url: str) -> dict:
    try:
        competitor = await resolve_place_from_url_or_text(competitor_url)
        place_id = competitor.get("place_id")
        if not place_id:
            raise GoalsSetupError(
                "Google Places did not return a place_id.",
                status_code=502,
            )

        return {
            "competitor_url": competitor_url,
            "place_id": place_id,
            "place": competitor,
            "error": None,
        }

    except (GooglePlacesError, GoalsSetupError) as exc:
        return {
            "competitor_url": competitor_url,
            "place_id": None,
            "place": None,
            "error": {
                "competitor_url": competitor_url,
                "status_code": getattr(exc, "status_code", 400),
                "error": str(exc),
            },
        }


async def _save_single_business_goals(payload: GoalsSetupRequest, business) -> dict:
    matched_business, own_place_ids = await _business_for_goals(
        user_id=payload.user_id,
        business_name=business.business_name,
        location=business.location,
    )
    selected_place_id = matched_business["place_id"]
    context = await get_latest_business_context(
        selected_place_id,
        user_id=payload.user_id,
    )

    competitor_place_ids: list[str] = []
    competitor_places: list[dict] = []
    competitor_errors: list[dict] = []

    resolved_competitors = await asyncio.gather(
        *(
            _resolve_competitor_place(competitor_url)
            for competitor_url in business.competitors_urls
        )
    )

    for resolved in resolved_competitors:
        if resolved["error"]:
            competitor_errors.append(resolved["error"])
            continue

        place_id = resolved["place_id"]

        if place_id in own_place_ids or place_id in competitor_place_ids:
            continue

        competitor_place_ids.append(place_id)
        competitor_places.append(resolved["place"])

    for place in competitor_places:
        await upsert_place_data(place)

    if not competitor_place_ids:
        error_details = "; ".join(
            f"{item['competitor_url']}: {item['error']}"
            for item in competitor_errors
        )

        message = (
            f"No competitor places could be fetched from competitors_urls "
            f"for {business.business_name} at {business.location}."
        )

        if error_details:
            message = f"{message} {error_details}"

        raise GoalsSetupError(message, status_code=400)

    updated_context = await _save_or_update_goals_context(
        context=context,
        matched_business=matched_business,
        user_id=payload.user_id,
        selected_place_id=selected_place_id,
        competitor_place_ids=competitor_place_ids,
        goals=business.goals,
        goals_input=business.model_dump(),
    )

    if not updated_context:
        raise GoalsSetupError(
            (
                "Could not update the saved business context for "
                f"{business.business_name} at {business.location}."
            ),
            status_code=500,
        )

    return {
        "status": "saved",
        "context_id": updated_context["id"],
        "business_name": updated_context.get("business_name"),
        "location": business.location,
        "place_id": selected_place_id,
        "goals": updated_context.get("goals", []),
        "competitors": [summarize_place(place) for place in competitor_places],
        "competitor_errors": competitor_errors,
    }


async def fetch_and_save_goals_setup(payload: GoalsSetupRequest) -> dict:
    results = []

    for business in payload.businesses:
        result = await _save_single_business_goals(payload, business)
        results.append(result)

    return {
        "status": "saved",
        "user_id": payload.user_id,
        "businesses": results,
    }
