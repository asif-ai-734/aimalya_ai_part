from fastapi import FastAPI 
from app.routes import overview, review_analysis, ai_insights, monthly_report
from app.routes import competitor_analysis

# from app.services.competitor_loader import find_competitors_from_place_json
# from app.services.place_loader import load_place_data

# place_data = load_place_data()

# competitors = find_competitors_from_place_json(place_data)


app= FastAPI(
    title="ReviewIQ",
    description= "AI Powere business review analytics",
    version= "1.0.0"
)

app.include_router(overview.router)
app.include_router(review_analysis.router)
app.include_router(ai_insights.router)
app.include_router(monthly_report.router)
app.include_router(competitor_analysis.router)

@app.get("/")
def root():
    return {"status": "ReviewIQ backend is running"}