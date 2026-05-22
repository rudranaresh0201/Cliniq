KNOWN_OUTBREAKS: dict[str, list[dict]] = {
    "Maharashtra": [
        {
            "disease": "Dengue",
            "severity": "HIGH",
            "message": "Dengue cases 40% above seasonal average in Mumbai",
            "source": "BMC Health Bulletin",
            "date": "2026-05",
        }
    ],
    "Kerala": [
        {
            "disease": "Leptospirosis",
            "severity": "MEDIUM",
            "message": "Post-flood leptospirosis advisory active",
            "source": "Kerala Health Dept",
            "date": "2026-05",
        }
    ],
}


def get_outbreak_alerts(state: str) -> list[dict]:
    return KNOWN_OUTBREAKS.get(state, [])
