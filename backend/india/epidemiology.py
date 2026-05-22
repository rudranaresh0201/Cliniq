from datetime import datetime

SEASONAL_DISEASE_WEIGHTS = {
    "monsoon": {
        "dengue": 0.85,
        "malaria": 0.75,
        "leptospirosis": 0.60,
        "cholera": 0.65,
        "typhoid": 0.70,
        "chikungunya": 0.75,
    },
    "winter": {
        "influenza": 0.80,
        "pneumonia": 0.75,
        "tuberculosis": 0.70,
        "cold": 0.85,
    },
    "summer": {
        "heat_stroke": 0.80,
        "food_poisoning": 0.75,
        "gastroenteritis": 0.70,
        "dehydration": 0.85,
    },
    "year_round": {
        "tuberculosis": 0.65,
        "typhoid": 0.55,
        "hepatitis_a": 0.50,
        "hepatitis_b": 0.45,
    },
}

STATE_DISEASE_PREVALENCE = {
    "Maharashtra": {
        "dengue": 0.80, "leptospirosis": 0.70,
        "malaria": 0.65, "tuberculosis": 0.75,
    },
    "Kerala": {
        "dengue": 0.85, "chikungunya": 0.80,
        "leptospirosis": 0.75, "nipah": 0.30,
    },
    "Delhi": {
        "dengue": 0.75, "chikungunya": 0.70,
        "typhoid": 0.65, "air_pollution_related": 0.80,
    },
    "West Bengal": {
        "malaria": 0.80, "dengue": 0.70,
        "cholera": 0.65, "kala_azar": 0.50,
    },
    "Rajasthan": {
        "malaria": 0.75, "dengue": 0.65,
        "heat_stroke": 0.85, "typhoid": 0.60,
    },
}

# Disease prior weights for prevalence-aware ranking (0.0–1.0)
DISEASE_PRIOR_WEIGHTS = {
    # Very common in India
    "dengue": 0.90,
    "dengue fever": 0.90,
    "malaria": 0.88,
    "typhoid": 0.85,
    "tuberculosis": 0.85,
    "viral fever": 0.92,
    "influenza": 0.88,
    "gastroenteritis": 0.87,
    "chikungunya": 0.82,
    "leptospirosis": 0.75,
    "hepatitis a": 0.75,
    "hepatitis e": 0.72,
    "pneumonia": 0.80,
    "urinary tract infection": 0.83,
    "common cold": 0.95,
    "food poisoning": 0.85,
    "anemia": 0.82,
    "vitamin d deficiency": 0.80,
    # Moderately common
    "appendicitis": 0.65,
    "migraine": 0.70,
    "hypertension": 0.75,
    "diabetes complication": 0.72,
    "asthma": 0.70,
    "chickenpox": 0.68,
    "measles": 0.60,
    # Uncommon — penalize unless strong evidence
    "autoimmune hepatitis": 0.25,
    "lupus": 0.20,
    "kawasaki disease": 0.15,
    "still disease": 0.12,
    "traps": 0.05,
    "tnf receptor associated periodic syndrome": 0.05,
    "pityriasis rosea": 0.30,
    "reactive arthritis": 0.25,
    "brucellosis": 0.20,
    "melioidosis": 0.10,
    "scrub typhus": 0.35,
}

SYMPTOM_CLUSTER_BOOSTS = {
    "dengue_cluster": {
        "keywords": ["fever", "rash", "body pain", "joint pain", "headache", "platelet"],
        "min_matches": 2,
        "boost_diseases": {
            "dengue": 0.18,
            "dengue fever": 0.18,
            "chikungunya": 0.12,
        },
        "reason": "boosted: fever+rash+pain cluster matches dengue/chikungunya pattern",
    },
    "mosquito_borne_cluster": {
        "keywords": ["fever", "chills", "sweating", "body pain", "headache"],
        "min_matches": 2,
        "season": "monsoon",
        "boost_diseases": {
            "malaria": 0.15,
            "dengue": 0.12,
            "dengue fever": 0.12,
            "chikungunya": 0.10,
        },
        "reason": "boosted: monsoon mosquito-borne disease pattern",
    },
    "gi_cluster": {
        "keywords": ["vomiting", "diarrhea", "stomach pain", "nausea", "loose motion"],
        "min_matches": 2,
        "boost_diseases": {
            "typhoid": 0.15,
            "gastroenteritis": 0.14,
            "food poisoning": 0.13,
            "hepatitis a": 0.10,
        },
        "reason": "boosted: GI symptom cluster matches enteric disease pattern",
    },
    "fever_headache_cluster": {
        "keywords": ["fever", "headache", "vomiting"],
        "min_matches": 3,
        "boost_diseases": {
            "dengue": 0.10,
            "typhoid": 0.10,
            "viral fever": 0.08,
            "malaria": 0.08,
        },
        "reason": "boosted: fever+headache+vomiting triad",
    },
    "respiratory_cluster": {
        "keywords": ["cough", "cold", "sore throat", "breathlessness", "chest pain"],
        "min_matches": 2,
        "boost_diseases": {
            "influenza": 0.14,
            "pneumonia": 0.12,
            "tuberculosis": 0.10,
            "covid": 0.10,
        },
        "reason": "boosted: respiratory symptom cluster",
    },
}

NON_ENDEMIC_DISEASES = {
    "monkeypox": 0.45,
    "mpox": 0.45,
    "ebola": 0.60,
    "marburg": 0.60,
    "west nile fever": 0.35,
    "yellow fever": 0.40,
    "zika": 0.30,
    "tnf receptor": 0.50,
    "traps": 0.50,
    "still disease": 0.45,
    "kawasaki": 0.40,
    "brucellosis": 0.35,
    "melioidosis": 0.30,
    "tularemia": 0.60,
    "plague": 0.60,
}

GENERIC_DISEASE_NAMES = [
    "viral infection",
    "bacterial infection",
    "infection",
    "fever",
    "illness",
    "disease",
    "syndrome",
]

INDIA_ENDEMIC_DISEASES = {
    "dengue": 0.92,
    "dengue fever": 0.92,
    "dengue hemorrhagic fever": 0.88,
    "malaria": 0.90,
    "plasmodium vivax": 0.85,
    "plasmodium falciparum": 0.85,
    "typhoid": 0.88,
    "typhoid fever": 0.88,
    "enteric fever": 0.85,
    "chikungunya": 0.85,
    "leptospirosis": 0.80,
    "tuberculosis": 0.88,
    "tb": 0.85,
    "hepatitis a": 0.78,
    "hepatitis e": 0.75,
    "cholera": 0.75,
    "scrub typhus": 0.72,
    "kala azar": 0.70,
    "visceral leishmaniasis": 0.70,
    "japanese encephalitis": 0.68,
    "viral fever": 0.82,
    "influenza": 0.80,
    "pneumonia": 0.78,
    "urinary tract infection": 0.80,
    "uti": 0.80,
    "gastroenteritis": 0.82,
    "food poisoning": 0.80,
    "anemia": 0.78,
}

# Location/symptom-aware boosting rules
LOCATION_SYMPTOM_BOOSTS = {
    "mumbai_fever_rash": {
        "trigger_keywords": ["fever", "rash", "body pain", "joint pain"],
        "trigger_states": ["Maharashtra"],
        "boost": {"dengue": 0.15, "chikungunya": 0.12, "malaria": 0.10},
    },
    "monsoon_fever": {
        "trigger_keywords": ["fever", "vomiting", "headache"],
        "trigger_season": "monsoon",
        "boost": {"dengue": 0.12, "malaria": 0.10, "typhoid": 0.08},
    },
    "child_fever": {
        "trigger_keywords": ["child", "baby", "infant", "fever", "vomiting"],
        "boost": {
            "viral fever": 0.15,
            "gastroenteritis": 0.12,
            "urinary tract infection": 0.10,
        },
        "penalize": {
            "traps": 0.40,
            "still disease": 0.30,
            "kawasaki disease": 0.20,
        },
    },
}


def get_current_season() -> str:
    month = datetime.now().month
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5, 6):
        return "summer"
    if month in (7, 8, 9, 10):
        return "monsoon"
    return "winter"  # November


def get_india_context(state: str = "Maharashtra") -> dict:
    season = get_current_season()
    seasonal_weights = SEASONAL_DISEASE_WEIGHTS.get(season, {})
    state_prevalence = STATE_DISEASE_PREVALENCE.get(state, {})

    # Combine seasonal + state weights to find top 3 high-risk diseases
    combined: dict[str, float] = {}
    for disease, w in seasonal_weights.items():
        combined[disease] = combined.get(disease, 0) + w
    for disease, w in state_prevalence.items():
        combined[disease] = combined.get(disease, 0) + w

    top3 = sorted(combined, key=lambda d: combined[d], reverse=True)[:3]

    parts = []
    for d in top3:
        pct = int(combined[d] / 2 * 100)  # normalise to 0-100
        parts.append(f"{d.replace('_', ' ').title()} ({pct}%)")

    context_string = (
        f"It is {season} season in {state}. "
        f"High risk: {', '.join(parts)}. "
        "Weight differential diagnoses accordingly."
    )

    return {
        "season": season,
        "state": state,
        "high_risk_diseases": top3,
        "seasonal_weights": seasonal_weights,
        "state_prevalence": state_prevalence,
        "context_string": context_string,
    }


def _get_disease_prior(disease_name: str) -> float:
    name_lower = disease_name.lower().strip()

    # Check endemic diseases first (highest priority)
    for key, weight in INDIA_ENDEMIC_DISEASES.items():
        if key in name_lower or name_lower in key:
            return weight

    # Check non-endemic diseases (penalty tier)
    for key, penalty in NON_ENDEMIC_DISEASES.items():
        if key in name_lower or name_lower in key:
            return penalty

    # Fall back to general prior weights
    for key, weight in DISEASE_PRIOR_WEIGHTS.items():
        if key in name_lower or name_lower in key:
            return weight

    return 0.50  # neutral prior


def _is_generic_name(disease_name: str) -> bool:
    name_lower = disease_name.lower().strip()
    for generic in GENERIC_DISEASE_NAMES:
        if name_lower == generic or name_lower == generic + "s":
            return True
    return False


def _apply_symptom_clusters(
    conditions: list[dict],
    query: str,
    season: str,
) -> tuple[list[dict], list[str]]:
    query_lower = query.lower()
    reasons: list[str] = []

    for cluster in SYMPTOM_CLUSTER_BOOSTS.values():
        if "season" in cluster and cluster["season"] != season:
            continue

        matches = sum(1 for kw in cluster["keywords"] if kw in query_lower)
        if matches < cluster["min_matches"]:
            continue

        for condition in conditions:
            name_lower = condition["name"].lower()
            for disease_key, boost_amount in cluster["boost_diseases"].items():
                if disease_key in name_lower or name_lower in disease_key:
                    condition["confidence"] = min(
                        95, condition["confidence"] + boost_amount * 100
                    )
                    reason = cluster["reason"]
                    if reason not in reasons:
                        reasons.append(reason)

    return conditions, reasons


def _apply_location_boosts(
    conditions: list[dict],
    query: str,
    state: str,
    season: str,
) -> list[dict]:
    query_lower = query.lower()

    for rule in LOCATION_SYMPTOM_BOOSTS.values():
        keywords = rule.get("trigger_keywords", [])
        if not any(kw in query_lower for kw in keywords):
            continue

        trigger_states = rule.get("trigger_states")
        if trigger_states and state not in trigger_states:
            continue

        trigger_season = rule.get("trigger_season")
        if trigger_season and season != trigger_season:
            continue

        boost_map: dict[str, float] = rule.get("boost", {})
        penalize_map: dict[str, float] = rule.get("penalize", {})

        for cond in conditions:
            name_lower = cond["name"].lower()
            for disease, delta in boost_map.items():
                if disease in name_lower or name_lower in disease:
                    cond["confidence"] = min(95, cond["confidence"] + delta * 100)
            for disease, delta in penalize_map.items():
                if disease in name_lower or name_lower in disease:
                    cond["confidence"] = max(5, cond["confidence"] - delta * 100)

    return conditions


def adjust_conditions_for_india(
    conditions: list[dict],
    india_context: dict,
    query: str = "",
) -> list[dict]:
    if not conditions:
        return conditions

    season = india_context.get("season", "summer")
    state = india_context.get("state", "Maharashtra")
    state_prevalence = india_context.get("state_prevalence", {})
    seasonal_weights = india_context.get("seasonal_weights", {})

    # Work on copies to avoid mutating caller's data
    conditions = [dict(c) for c in conditions]

    for condition in conditions:
        name = condition.get("name", "")
        confidence = float(condition.get("confidence", 50))
        rerank_reasons: list[str] = []

        # Step 1 — Prior weight adjustment (endemic vs non-endemic)
        prior = _get_disease_prior(name)
        if prior >= 0.80:
            boost = (prior - 0.50) * 25  # up to +12.5 pts
            confidence = min(95, confidence + boost)
            rerank_reasons.append(f"India endemic disease (prior={prior:.2f})")
        elif prior <= 0.45:
            if confidence < 75:
                penalty = (0.50 - prior) * 40  # up to -8 pts
                confidence = max(5, confidence - penalty)
                rerank_reasons.append(
                    f"non-endemic/rare disease penalized (prior={prior:.2f})"
                )

        # Step 2 — Generic disease penalty
        if _is_generic_name(name):
            confidence = max(5, confidence - 8)
            rerank_reasons.append("generic diagnosis name penalized")

        # Step 3 — Seasonal + state boost with partial matching
        name_lower = name.lower()
        seasonal_w = seasonal_weights.get(name_lower, 0)
        if seasonal_w == 0:
            for key, w in seasonal_weights.items():
                if key in name_lower or name_lower in key:
                    seasonal_w = w
                    break

        state_w = state_prevalence.get(name_lower, 0)
        if state_w == 0:
            for key, w in state_prevalence.items():
                if key in name_lower or name_lower in key:
                    state_w = w
                    break

        if seasonal_w > 0 or state_w > 0:
            regional_boost = (seasonal_w + state_w) * 7
            confidence = min(95, confidence + regional_boost)
            if seasonal_w > 0:
                rerank_reasons.append(
                    f"boosted: {season} season prevalence ({seasonal_w:.0%})"
                )
            if state_w > 0:
                rerank_reasons.append(
                    f"boosted: state-level prevalence ({state_w:.0%})"
                )

        condition["confidence"] = round(confidence, 1)
        condition["reranking_reasons"] = rerank_reasons

    # Step 4 — Symptom cluster boost
    conditions, _ = _apply_symptom_clusters(conditions, query, season)

    # Step 5 — Location-aware keyword boost
    conditions = _apply_location_boosts(conditions, query, state, season)

    # Step 6 — Final clamp + sort
    for c in conditions:
        c["confidence"] = round(max(1, min(95, float(c["confidence"]))), 1)

    conditions.sort(key=lambda x: x["confidence"], reverse=True)

    return conditions
