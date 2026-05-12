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
        competitor_scores = [score for name, score in scores if name != my_name]
        avg_source = competitor_scores or [score for _, score in scores]
        avg= round(sum(avg_source) / len(avg_source), 1)
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


def _number(value, default: float = 0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _display_score(value: float | int) -> float | int:
    rounded = round(value, 1)
    return int(rounded) if rounded.is_integer() else rounded


def _metric_title(metric: str) -> str:
    titles = {
        "reviews": "Review Volume",
        "response_rate": "Response Rate",
    }
    return titles.get(metric, metric.replace("_", " ").title())


def _competitor_excel_evidence_record(
    *,
    evidence_id: str,
    title: str,
    leader: str,
    metric: str,
    competitor_value: float,
    my_value: float,
    source: str,
) -> dict:
    gap = round(competitor_value - my_value, 1)
    relationship = "competitor_leads" if gap > 0 else "competitor_strength"

    return {
        "evidence_id": evidence_id,
        "title": title,
        "leader": leader,
        "metric": metric,
        "source": source,
        "competitor_value": _display_score(competitor_value),
        "my_value": _display_score(my_value),
        "gap": _display_score(gap),
        "relationship": relationship,
    }


def build_competitor_excel_evidence(
    my_business: dict,
    competitors: list[dict],
) -> list[dict]:
    if not competitors:
        return []

    evidence = []
    business_metrics = ("rating", "reviews", "sentiment", "response_rate")

    for metric in business_metrics:
        my_value = _number(my_business.get(metric))
        leader = max(competitors, key=lambda item: _number(item.get(metric)))
        competitor_value = _number(leader.get(metric))

        evidence.append(
            _competitor_excel_evidence_record(
                evidence_id=f"metric_{metric}",
                title=_metric_title(metric),
                leader=leader.get("name", "Competitor"),
                metric=metric,
                competitor_value=competitor_value,
                my_value=my_value,
                source="performance_comparison",
            )
        )

    for metric, my_score in my_business.get("criteria", {}).items():
        leader = max(
            competitors,
            key=lambda item: _number(item.get("criteria", {}).get(metric)),
        )
        competitor_value = _number(leader.get("criteria", {}).get(metric))

        evidence.append(
            _competitor_excel_evidence_record(
                evidence_id=f"criteria_{metric}",
                title=_metric_title(metric),
                leader=leader.get("name", "Competitor"),
                metric=metric,
                competitor_value=competitor_value,
                my_value=_number(my_score),
                source="criteria_comparison",
            )
        )

    evidence.sort(
        key=lambda item: (
            item["relationship"] != "competitor_leads",
            -_number(item["gap"]),
            -_number(item["competitor_value"]),
        )
    )
    return evidence


def _strength_for_area(area: str) -> str:
    strengths = {
        "Service": "Feature service quality in review responses and campaigns.",
        "Quality": "Highlight this quality edge in marketing materials.",
        "Atmosphere": "Use atmosphere as a differentiator in local promotions.",
        "Value": "Promote value-led offers while protecting margin.",
        "Cleanliness": "Showcase cleanliness in photos, replies, and store standards.",
    }
    return strengths.get(area, f"Use {area.lower()} as a competitive proof point.")


def extract_advantages(criteria_comparison: list, my_name: str):
    competitive_advantages = []

    for c in criteria_comparison:
        area = c["criteria"]
        my_score = c["my_score"]
        competitor_avg = c["competitor_avg"]

        if c["leader"]["name"]== my_name:
            competitive_advantages.append({
                "title": area,
                "description": (
                    f"You lead in {area.lower()} with {my_score} vs "
                    f"competitor average of {competitor_avg}."
                ),
                "strength": _strength_for_area(area),
                "my_score": my_score,
                "competitor_avg": competitor_avg,
            })
    
    return [], competitive_advantages
