from app.db.business_context_store import (
    get_latest_business_context,
    get_latest_business_context_by_name,
    update_business_context_goals,
)
from app.db.place_store import upsert_place_data
from app.schemas.goals_set_up_py import GoalsSetupRequest
from app.services.google_places_service import (
    GooglePlacesError,
    resolve_place_from_url_or_text,
    summarize_place,
)


class GoalsSetupError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


async def _context_for_goals(payload: GoalsSetupRequest) -> dict:
    context = await get_latest_business_context_by_name(payload.business_name)
    if context:
        return context

    context = await get_latest_business_context()
    if context:
        return context

    raise GoalsSetupError(
        "Submit POST /businesses/fetch before setting goals.",
        status_code=404,
    )


async def fetch_and_save_goals_setup(payload: GoalsSetupRequest) -> dict:
    context = await _context_for_goals(payload)
    own_place_ids = set(context.get("place_ids", []))
    competitor_place_ids: list[str] = []
    competitor_places: list[dict] = []
    competitor_errors: list[dict] = []

    for competitor_url in payload.competitors_urls:
        try:
            competitor = await resolve_place_from_url_or_text(competitor_url)
            place_id = competitor.get("place_id")
            if not place_id:
                raise GoalsSetupError(
                    "Google Places did not return a place_id.",
                    status_code=502,
                )
            if place_id in own_place_ids or place_id in competitor_place_ids:
                continue

            await upsert_place_data(competitor)
            competitor_place_ids.append(place_id)
            competitor_places.append(competitor)
        except (GooglePlacesError, GoalsSetupError) as exc:
            status_code = getattr(exc, "status_code", 400)
            competitor_errors.append(
                {
                    "competitor_url": competitor_url,
                    "status_code": status_code,
                    "error": str(exc),
                }
            )

    if not competitor_place_ids:
        error_details = "; ".join(
            f"{item['competitor_url']}: {item['error']}"
            for item in competitor_errors
        )
        message = "No competitor places could be fetched from competitors_urls."
        if error_details:
            message = f"{message} {error_details}"
        raise GoalsSetupError(
            message,
            status_code=400,
        )

    updated_context = await update_business_context_goals(
        context_id=context["id"],
        competitor_place_ids=competitor_place_ids,
        report_frequency=payload.report_frequency,
        goals=payload.goals,
        goals_input=payload.model_dump(),
    )
    if not updated_context:
        raise GoalsSetupError(
            "Could not update the saved business context.",
            status_code=500,
        )

    return {
        "status": "saved",
        "context_id": updated_context["id"],
        "business_name": updated_context.get("business_name"),
        "report_frequency": updated_context.get("report_frequency"),
        "goals": updated_context.get("goals", []),
        "competitors": [summarize_place(place) for place in competitor_places],
        "competitor_errors": competitor_errors,
    }
