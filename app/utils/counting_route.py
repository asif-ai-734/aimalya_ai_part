import json
from typing import Callable
from fastapi import Request, Response
from fastapi.routing import APIRoute
from app.db.route_hit_store import increment_and_get_hit_count, record_route_event

class CountingRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_handler = super().get_route_handler()

        async def custom_handler(request: Request) -> Response:
            # 1. Get user_id from query params or default to "anonymous"
            user_id = request.query_params.get("user_id") or "anonymous"
            
            # 2. Increment and get count
            count = await increment_and_get_hit_count(user_id, request.url.path)
            
            # 3. Call the original route handler
            response: Response = await original_handler(request)
            if response.status_code < 400:
                await record_route_event(user_id, request.url.path)
            
            # 4. If it's a JSON response, inject the count
            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                # We need to access the body. response.body is usually available for JSONResponse
                try:
                    # For FastAPI's JSONResponse, the body is already in .body
                    body = response.body
                    data = json.loads(body)
                    
                    if isinstance(data, dict):
                        data["count"] = count
                    elif isinstance(data, list):
                        data = {"data": data, "count": count}
                    
                    new_content = json.dumps(data).encode("utf-8")
                    
                    # Remove Content-Length so it's recalculated for the new content
                    headers = dict(response.headers)
                    headers.pop("content-length", None)
                    
                    return Response(
                        content=new_content,
                        status_code=response.status_code,
                        headers=headers,
                        media_type=content_type
                    )
                except Exception:
                    # Fallback to original if parsing fails
                    pass
            
            # For non-JSON, we can still add the count to headers as a backup
            response.headers["X-Route-Hit-Count"] = str(count)
            return response

        return custom_handler
