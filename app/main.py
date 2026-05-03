from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.routes import overview, review_analysis, ai_insights, monthly_report
from app.routes import competitor_analysis
from app.routes import business_setup
from app.routes import goals_set_up_py
from app.services.place_loader import PlaceDataNotFound

# from app.services.competitor_loader import find_competitors_from_place_json
# from app.services.place_loader import load_place_data

# place_data = load_place_data()

# competitors = find_competitors_from_place_json(place_data)


app= FastAPI(
    title="ReviewIQ",
    description= "AI Powere business review analytics",
    version= "1.0.0"
)

app.include_router(business_setup.router)
app.include_router(goals_set_up_py.router)
app.include_router(overview.router)
app.include_router(review_analysis.router)
app.include_router(ai_insights.router)
app.include_router(monthly_report.router)
app.include_router(competitor_analysis.router)



@app.exception_handler(PlaceDataNotFound)
async def place_data_not_found_handler(
    request: Request,
    exc: PlaceDataNotFound,
):
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )

@app.get("/")
def root():
    return {"status": "ReviewIQ backend is running"}
