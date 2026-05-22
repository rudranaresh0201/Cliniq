EMERGENCY_KEYWORDS = [
    "chest pain", "heart attack", "cardiac arrest", "can't breathe", "difficulty breathing",
    "shortness of breath", "choking",
    "stroke", "face drooping", "sudden confusion",
    "seizure", "unconscious", "not responding",
    "severe bleeding", "coughing blood", "vomiting blood",
    "overdose", "poisoning", "anaphylaxis",
    "suicidal", "kill myself", "infant not breathing"
]

EMERGENCY_RESPONSE = {
    "triage": "EMERGENCY",
    "color": "red",
    "message": "This sounds like a medical emergency.",
    "immediate_action": "Call 112 immediately. Do not wait.",
    "do_not": "Do not use this app. Go to emergency room NOW.",
    "disclaimer": "Automated safety check. Not AI-generated."
}

def check_emergency(text: str) -> dict | None:
    text_lower = text.lower()
    for keyword in EMERGENCY_KEYWORDS:
        if keyword in text_lower:
            return {**EMERGENCY_RESPONSE, "triggered_by": keyword}
    return None
