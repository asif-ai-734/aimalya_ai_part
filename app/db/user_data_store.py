import asyncio

from app.db.actionable_recommendation_store import (
    _init_actionable_recommendation_db_sync,
)
from app.db.business_context_store import _init_business_context_sync
from app.db.business_store import _init_user_business_db_sync
from app.db.database import connect
from app.db.route_hit_store import _init_route_hit_db_sync


def _delete_user_data_sync(user_id: str) -> dict:
    _init_business_context_sync()
    _init_user_business_db_sync()
    _init_actionable_recommendation_db_sync()
    _init_route_hit_db_sync()

    with connect() as conn:
        deleted_user_businesses = conn.execute(
            "DELETE FROM user_businesses WHERE user_id = ?",
            (user_id,),
        ).rowcount
        deleted_business_contexts = conn.execute(
            "DELETE FROM business_contexts WHERE user_id = ?",
            (user_id,),
        ).rowcount
        deleted_actionable_recommendations = conn.execute(
            "DELETE FROM actionable_recommendations WHERE user_id = ?",
            (user_id,),
        ).rowcount
        deleted_route_hit_events = conn.execute(
            "DELETE FROM route_hit_events WHERE user_id = ?",
            (user_id,),
        ).rowcount
        deleted_route_hits = conn.execute(
            "DELETE FROM route_hits WHERE user_id = ?",
            (user_id,),
        ).rowcount

    deleted_counts = {
        "user_businesses": deleted_user_businesses,
        "business_contexts": deleted_business_contexts,
        "actionable_recommendations": deleted_actionable_recommendations,
        "route_hit_events": deleted_route_hit_events,
        "route_hits": deleted_route_hits,
    }

    return {
        "user_id": user_id,
        "deleted": deleted_counts,
        "deleted_count": sum(deleted_counts.values()),
    }


async def delete_user_data(user_id: str) -> dict:
    return await asyncio.to_thread(_delete_user_data_sync, user_id)
