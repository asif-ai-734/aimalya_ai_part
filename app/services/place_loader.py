#app.services.place_loader.py
from app.db.business_context_store import get_latest_business_context
from app.db.place_store import get_place_data


class PlaceDataNotFound(LookupError):
    pass


async def load_place_data(place_id: str | None = None):
    if place_id:
        place = await get_place_data(place_id)
        if place:
            return place

    context = await get_latest_business_context(place_id)
    if context:
        place = await get_place_data(context["primary_place_id"])
        if place:
            return place

    place = await get_place_data(place_id)
    if place:
        return place

    raise PlaceDataNotFound(
        "No saved Google Places data found. Submit POST /businesses/fetch first."
    )
