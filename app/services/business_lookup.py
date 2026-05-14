from app.db.business_store import get_user_businesses
from app.utils.business_matching import business_matches


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
