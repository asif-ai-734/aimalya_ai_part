from fastapi import FastAPI 
from app.routes import overview, review_analysis, ai_insights, monthly_report

app= FastAPI(
    title="ReviewIQ",
    description= "AI Powere business review analytics",
    version= "1.0.0"
)

app.include_router(overview.router)
app.include_router(review_analysis.router)
app.include_router(ai_insights.router)
app.include_router(monthly_report.router)

@app.get("/")
def root():
    return {"status": "ReviewIQ backend is running"}