#app.services.competitor_analysis.py


def estimate_criteria_scores(rating: float, price_level: int):
    base= max(min((rating / 5) * 100, 95), 40)


    return {
        "service": round(base / 20, 1),
        "quality": round((base + 5) / 20, 1),
        "atmosphere": round((base - 2) / 20, 1),
        "value": round((base - price_level * 8) / 20, 1),
        "cleanliness": round((base + 3) / 20, 1)
    }


def build_performance_comparison(businesses: list):
    metrics = ["rating", "reviews", "sentiment", "response_rate"]
    return {
        metric: [{"name": b["name"], "value": b[metric]} for b in businesses]
        for metric in metrics
    }

def build_category_radar(businesses: list):
    radar = {}
    for b in businesses:
        radar[b["name"]] = {
            k.capitalize(): round((v /5) * 100)
            for k, v in b["criteria"].items()
        }
    return radar



def build_criteria_comparison(businesses: list, my_name: str):
    keys = businesses[0]["criteria"].keys()
    result= []


    for key in keys:
        scores= [(b["name"], b["criteria"][key]) for b in businesses]
        avg= round(sum(s for _, s in scores) / len(scores) / len(scores), 1)
        leader= max(scores, key= lambda x:x[1])

        my_score = next(
            b["criteria"][key]
            for b in businesses
            if b["name"] == my_name
            )
        
        result.append({
            "criteria": key.replace("_", " ").title(),
            "my_score": my_score,
            "competitor_avg": avg,
            "leader": {
                "name": leader[0],
                "score": leader[1]
            }
        })

    return result 


def extract_advantages(criteria_comparison: list, my_name: str):
    competitors_excel = []
    my_advantages= []

    for c in criteria_comparison:
        if c["leader"]["name"]== my_name:
            my_advantages.append({
                "area": c["criteria"],
                "my_score": c["my_score"],
                "competitor_avg": c["competitor_avg"]
            })
        
        else:
            competitors_excel.append({
                "area": c["criteria"],
                "leader": c["leader"]["name"],
                "leader_score": c["leader"]["score"],
                "my_score": c["my_score"]
            })
    
    return competitors_excel, my_advantages
