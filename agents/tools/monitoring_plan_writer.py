"""
ClinIQ 2.0 — monitoring_plan_writer tool.

Generates a structured multi-day WhatsApp monitoring plan after every
consultation.  Selects a disease-specific template (dengue, typhoid,
malaria, TB, viral fever, or general), builds dated Checkpoint objects
in the correct language, writes the plan to Supabase, and returns the
full plan payload to the pipeline.

This is the core of the ClinIQ autonomous patient-watch system: once a
plan exists, the Watch Worker wakes daily, finds due checkpoints, and
sends WhatsApp messages automatically.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from db.models import (
    Checkpoint,
    CheckpointAgentEvaluation,
    CheckpointRiskConditions,
    MonitoringPlan,
)
from db.supabase_client import create_monitoring_plan
from db.timeline import write_timeline_event as _tl_write

logger = logging.getLogger("cliniq.tools.monitoring_plan_writer")

# ---------------------------------------------------------------------------
# CheckpointTemplate — blueprint for one day's check-in
# ---------------------------------------------------------------------------


@dataclass
class CheckpointTemplate:
    day_offset: int
    questions_en: list[str]
    questions_hi: list[str]
    escalate_if: list[str]
    watch_if: list[str]
    resolve_if: list[str]


# ---------------------------------------------------------------------------
# MonitoringTemplate — full disease-specific plan blueprint
# ---------------------------------------------------------------------------


@dataclass
class MonitoringTemplate:
    name: str
    day_offsets: list[int]
    checkpoints: dict[int, CheckpointTemplate]


# ===========================================================================
# TEMPLATE DEFINITIONS — module-level constants, tuned per disease
# ===========================================================================

# ---------------------------------------------------------------------------
# DENGUE
# ---------------------------------------------------------------------------

DENGUE_TEMPLATE = MonitoringTemplate(
    name="dengue_monitoring",
    day_offsets=[1, 2, 3, 5, 7],
    checkpoints={
        1: CheckpointTemplate(
            day_offset=1,
            questions_en=[
                "Do you still have fever?",
                "Have you noticed any rash or red spots on your body?",
                "Any bleeding from gums, nose, or in urine?",
                "Are you able to drink water and fluids?",
            ],
            questions_hi=[
                "Kya abhi bhi bukhar hai?",
                "Kya shareer par koi laal daane ya rash aaye hain?",
                "Muh, naak se khoon ya peshab mein khoon to nahi?",
                "Kya aap paani aur liquid pi pa rahe hain?",
            ],
            escalate_if=[
                "bleeding from any site reported",
                "cannot drink fluids or vomiting everything",
                "extreme weakness or fainting",
                "severe abdominal pain",
            ],
            watch_if=[
                "fever persisting beyond day 4",
                "platelet count not rechecked",
                "rash spreading",
            ],
            resolve_if=[
                "fever gone for 24 hours",
                "eating and drinking normally",
                "no bleeding or rash",
            ],
        ),
        2: CheckpointTemplate(
            day_offset=2,
            questions_en=[
                "How is your fever compared to yesterday?",
                "Any vomiting or nausea today?",
                "Do you have pain when pressing your stomach?",
                "Have you had your platelet count checked?",
            ],
            questions_hi=[
                "Kal ke mukable aaj bukhar kaisa hai?",
                "Kya aaj ulti ya ji machalana ho raha hai?",
                "Pet dabane par dard hota hai?",
                "Kya platelets check karwaye?",
            ],
            escalate_if=[
                "bleeding from any site",
                "platelet count below 50000",
                "severe abdominal pain or tenderness",
                "not urinating for more than 6 hours",
            ],
            watch_if=[
                "fever same or worse",
                "vomiting more than twice",
                "platelets not checked yet",
            ],
            resolve_if=[
                "fever reducing",
                "no vomiting",
                "tolerating fluids well",
            ],
        ),
        3: CheckpointTemplate(
            day_offset=3,
            questions_en=[
                "Is the fever coming down now?",
                "Any new bleeding or red spots?",
                "How many times have you urinated today?",
                "Are you feeling stronger or weaker than yesterday?",
            ],
            questions_hi=[
                "Kya bukhar ab kam ho raha hai?",
                "Koi naya khoon ya laal daane to nahi aaye?",
                "Aaj kitni baar peshab hua?",
                "Kal se zyada taaqat mehsoos ho rahi hai ya kam?",
            ],
            escalate_if=[
                "fever above 104F on day 3",
                "any bleeding reported",
                "urinating less than twice in 24 hours",
                "extreme fatigue or cannot stand",
            ],
            watch_if=[
                "fever plateau not breaking",
                "reduced urine output",
            ],
            resolve_if=[
                "fever clearly reducing",
                "normal urine output",
                "appetite returning",
            ],
        ),
        5: CheckpointTemplate(
            day_offset=5,
            questions_en=[
                "Are you feeling better overall?",
                "Any weakness or fatigue still?",
                "Appetite back to normal?",
                "Any joint pain or body aches still?",
            ],
            questions_hi=[
                "Overall kaisa feel ho raha hai?",
                "Abhi bhi kamzori ya thakan hai?",
                "Bhook wapas aa gayi?",
                "Jodon mein ya sharir mein dard abhi bhi hai?",
            ],
            escalate_if=[
                "fever returned after being gone",
                "new symptoms appearing",
                "extreme weakness continuing",
            ],
            watch_if=[
                "persistent fatigue beyond day 5",
                "appetite not returning",
            ],
            resolve_if=[
                "feeling significantly better",
                "eating normally",
                "fever gone for 48 hours",
            ],
        ),
        7: CheckpointTemplate(
            day_offset=7,
            questions_en=[
                "Are you fully recovered?",
                "Back to normal activities?",
                "Any lingering symptoms we should know about?",
            ],
            questions_hi=[
                "Kya aap bilkul theek ho gaye?",
                "Kya normal kaam karne lage hain?",
                "Koi bhi takleef jo abhi bhi ho?",
            ],
            escalate_if=[
                "still having fever on day 7",
                "new complications reported",
            ],
            watch_if=[
                "prolonged fatigue",
                "any new symptoms",
            ],
            resolve_if=[
                "fully recovered",
                "no symptoms",
                "back to normal activities",
            ],
        ),
    },
)

# ---------------------------------------------------------------------------
# TYPHOID
# ---------------------------------------------------------------------------

TYPHOID_TEMPLATE = MonitoringTemplate(
    name="typhoid_monitoring",
    day_offsets=[2, 4, 7, 10, 14],
    checkpoints={
        2: CheckpointTemplate(
            day_offset=2,
            questions_en=[
                "Is your fever rising each day or staying the same?",
                "Do you have pain or discomfort in your stomach?",
                "How are your bowel movements — loose stools or constipation?",
                "Do you have a bad headache?",
            ],
            questions_hi=[
                "Kya bukhar roz badhta hai ya ek jaisa rehta hai?",
                "Pet mein dard ya takleef hai?",
                "Latrine kaisi hai — dast hai ya kabz?",
                "Sar mein tez dard hai?",
            ],
            escalate_if=[
                "sudden severe abdominal pain with rigid hard stomach — possible perforation",
                "fever above 104F not responding to paracetamol",
                "confusion or altered mental status",
            ],
            watch_if=[
                "fever rising in step-ladder pattern",
                "abdominal pain gradually worsening",
            ],
            resolve_if=[
                "fever stable and not rising further",
                "no severe abdominal pain",
                "able to eat and drink",
            ],
        ),
        4: CheckpointTemplate(
            day_offset=4,
            questions_en=[
                "Are you taking your antibiotics exactly as prescribed — no missed doses?",
                "Is the fever lower now compared to day 1?",
                "How is your appetite — able to eat?",
                "How many times are you passing stool per day?",
            ],
            questions_hi=[
                "Kya aap dawai bilkul sahi tarah le rahe hain — koi dose miss to nahi?",
                "Kya bukhar pehle din se kam hua hai?",
                "Bhook kaisi hai — kuch kha pa rahe hain?",
                "Din mein kitni baar latrine ho rahi hai?",
            ],
            escalate_if=[
                "fever not reducing at all after 4 days of antibiotics",
                "sudden severe abdominal pain — perforation risk",
                "blood in stool",
            ],
            watch_if=[
                "fever reducing but very slowly",
                "still barely eating or drinking",
            ],
            resolve_if=[
                "fever clearly lower than day 1",
                "completing antibiotic course without missing doses",
                "appetite beginning to return",
            ],
        ),
        7: CheckpointTemplate(
            day_offset=7,
            questions_en=[
                "Is the fever mostly gone now?",
                "Still taking all prescribed antibiotics?",
                "Any weakness or fatigue?",
                "Eating and drinking normally?",
            ],
            questions_hi=[
                "Kya bukhar ab zyaadatar chala gaya?",
                "Kya ab bhi sari dawaiyan le rahe hain?",
                "Kamzori ya thakan hai?",
                "Khana-pani theek se ho raha hai?",
            ],
            escalate_if=[
                "fever returning after briefly improving — relapse sign",
                "stopping antibiotics early",
            ],
            watch_if=[
                "fever not fully gone at day 7",
                "very low energy and appetite",
            ],
            resolve_if=[
                "fever gone for 48 hours",
                "completing antibiotic course",
                "eating and drinking well",
            ],
        ),
        10: CheckpointTemplate(
            day_offset=10,
            questions_en=[
                "How are you feeling — better than day 7?",
                "Did you complete the full antibiotic course?",
                "Any return of fever in the last 2 days?",
                "Any abdominal discomfort?",
            ],
            questions_hi=[
                "Kaisa feel ho raha hai — day 7 se behtar?",
                "Kya poori antibiotic course complete ki?",
                "Pichle 2 din mein bukhar wapas to nahi aaya?",
                "Pet mein koi takleef?",
            ],
            escalate_if=[
                "fever returned after apparent recovery — typhoid relapse",
                "new abdominal symptoms",
            ],
            watch_if=[
                "persistent fatigue and weakness",
                "antibiotics not completed",
            ],
            resolve_if=[
                "full antibiotic course completed",
                "no fever for 5 or more days",
                "energy and appetite returning",
            ],
        ),
        14: CheckpointTemplate(
            day_offset=14,
            questions_en=[
                "Are you fully recovered now?",
                "Any fever in the past week?",
                "Back to normal diet and activity?",
                "Any ongoing stomach pain or loose stools?",
            ],
            questions_hi=[
                "Kya ab poori tarah theek ho gaye?",
                "Pichle hafte mein koi bukhar aaya?",
                "Khana aur kaam sab normal ho gaya?",
                "Pet dard ya dast abhi bhi hai?",
            ],
            escalate_if=[
                "fever returning at day 14 — late relapse",
                "any new concerning symptoms",
            ],
            watch_if=[
                "still fatigued at 2 weeks",
                "recurring loose stools",
            ],
            resolve_if=[
                "fully recovered with no fever for 1 week",
                "back to normal activities",
                "no gastrointestinal complaints",
            ],
        ),
    },
)

# ---------------------------------------------------------------------------
# VIRAL FEVER
# ---------------------------------------------------------------------------

VIRAL_FEVER_TEMPLATE = MonitoringTemplate(
    name="viral_fever_monitoring",
    day_offsets=[2, 5, 7],
    checkpoints={
        2: CheckpointTemplate(
            day_offset=2,
            questions_en=[
                "Is the fever better, same, or worse compared to when it started?",
                "Are you drinking enough water and fluids?",
                "Any appetite at all?",
                "Any new symptoms since we last spoke — rash, difficulty breathing, severe headache?",
            ],
            questions_hi=[
                "Bukhar shuru se ab kaisa hai — behtar, same ya zyada?",
                "Kya paani aur liquid theek se pi rahe hain?",
                "Kuch khane ka mann hai?",
                "Koi naya lakshan — rash, saans lene mein takleef, tez sar dard?",
            ],
            escalate_if=[
                "difficulty breathing or chest pain developing",
                "severe headache with neck stiffness — meningitis red flag",
                "fever above 103F not responding to paracetamol",
                "unable to drink any fluids",
            ],
            watch_if=[
                "fever not improving at all by day 2",
                "appetite completely absent",
            ],
            resolve_if=[
                "fever reducing",
                "drinking fluids well",
                "feeling slightly better",
            ],
        ),
        5: CheckpointTemplate(
            day_offset=5,
            questions_en=[
                "Is the fever gone or still present?",
                "Feeling better than day 2?",
                "Eating and drinking normally now?",
                "Any body aches or fatigue still?",
            ],
            questions_hi=[
                "Kya bukhar chala gaya ya abhi bhi hai?",
                "Day 2 se behtar feel ho raha hai?",
                "Khana-pina normal ho gaya?",
                "Shareer mein dard ya thakan abhi bhi hai?",
            ],
            escalate_if=[
                "fever still present and not improving at day 5",
                "any new symptoms such as rash or breathing difficulty",
            ],
            watch_if=[
                "fever improving but still not gone",
                "persistent fatigue",
            ],
            resolve_if=[
                "fever gone or nearly gone",
                "eating and drinking normally",
                "energy returning",
            ],
        ),
        7: CheckpointTemplate(
            day_offset=7,
            questions_en=[
                "Are you fully recovered?",
                "Any fever in the past 48 hours?",
                "Back to normal activities?",
            ],
            questions_hi=[
                "Kya aap poori tarah theek ho gaye?",
                "Pichle 2 din mein koi bukhar?",
                "Normal kaam mein wapas aa gaye?",
            ],
            escalate_if=[
                "fever still present beyond day 7 — needs investigation",
                "worsening rather than improving",
            ],
            watch_if=[
                "prolonged fatigue beyond 1 week",
            ],
            resolve_if=[
                "fever-free for 48 hours",
                "fully recovered",
                "back to normal activities",
            ],
        ),
    },
)

# ---------------------------------------------------------------------------
# MALARIA
# ---------------------------------------------------------------------------

MALARIA_TEMPLATE = MonitoringTemplate(
    name="malaria_monitoring",
    day_offsets=[1, 2, 3, 7],
    checkpoints={
        1: CheckpointTemplate(
            day_offset=1,
            questions_en=[
                "Did you have a fever cycle today — did the fever come and then break with sweating?",
                "Did you have severe chills or shaking before the fever?",
                "Have you started your malaria medication?",
                "Any vomiting that is preventing you from taking medication?",
            ],
            questions_hi=[
                "Aaj bukhar aaya aur phir paseena aa kar gaya?",
                "Bukhar se pehle tez kaanpna hua?",
                "Malaria ki dawai shuru kar di?",
                "Ulti ho rahi hai jo dawai lene nahi de rahi?",
            ],
            escalate_if=[
                "confusion or unusual behavior — cerebral malaria sign",
                "seizure or convulsion",
                "unable to take oral medication due to vomiting",
                "yellow eyes developing — blackwater fever concern",
            ],
            watch_if=[
                "fever cycle not clearly defined yet",
                "vomiting once but able to keep medication down",
            ],
            resolve_if=[
                "started medication and tolerating it",
                "fever cycle regular and predictable",
                "no cerebral symptoms",
            ],
        ),
        2: CheckpointTemplate(
            day_offset=2,
            questions_en=[
                "How many fever cycles since yesterday?",
                "Are you taking every dose of antimalarial medication on time?",
                "Any confusion, severe headache, or unusual behavior?",
                "Are you able to drink fluids between fever episodes?",
            ],
            questions_hi=[
                "Kal se aaj tak kitni baar bukhar aaya?",
                "Kya malaria ki dawai poori tarah waqt par le rahe hain?",
                "Koi ghbarahat, tez sar dard, ya ajeeb harkat?",
                "Bukhar ke beech mein paani pi pa rahe hain?",
            ],
            escalate_if=[
                "any confusion or altered consciousness",
                "fever cycles becoming more frequent",
                "yellow eyes or dark colored urine",
            ],
            watch_if=[
                "missing medication doses",
                "fever not following expected pattern",
            ],
            resolve_if=[
                "taking all medication correctly",
                "fever cycles regular and not worsening",
                "mentally alert and drinking fluids",
            ],
        ),
        3: CheckpointTemplate(
            day_offset=3,
            questions_en=[
                "Is the fever responding to treatment — are the cycles less severe?",
                "Still taking all malaria medication without missing doses?",
                "Any new symptoms — yellow eyes, very dark urine, difficulty breathing?",
                "How is your energy level?",
            ],
            questions_hi=[
                "Kya dawai ka asar ho raha hai — bukhar thoda kam ho raha hai?",
                "Abhi bhi sari dawai bina miss kiye le rahe hain?",
                "Koi naya lakshan — aankhon mein peelaahat, kaala peshab, saans lene mein takleef?",
                "Taaqat kaisi hai?",
            ],
            escalate_if=[
                "no improvement in fever after 3 days of antimalarials — drug resistance possible",
                "yellow eyes or dark urine appearing",
                "any neurological symptoms",
            ],
            watch_if=[
                "improvement slower than expected",
                "extreme fatigue and weakness",
            ],
            resolve_if=[
                "fever cycles clearly less severe",
                "tolerating all medication",
                "energy improving",
            ],
        ),
        7: CheckpointTemplate(
            day_offset=7,
            questions_en=[
                "Are you fully recovered from malaria?",
                "Did you complete the full antimalarial course?",
                "Any return of fever or chills?",
                "Still feeling weak or fatigued?",
            ],
            questions_hi=[
                "Kya malaria se poori tarah theek ho gaye?",
                "Poori dawai ka course complete kiya?",
                "Koi bukhar ya kaanpna wapas aaya?",
                "Abhi bhi kamzori ya thakan mehsoos ho rahi hai?",
            ],
            escalate_if=[
                "fever returning after apparent recovery — relapse",
                "extreme weakness not improving at 1 week",
            ],
            watch_if=[
                "persistent fatigue — common after malaria",
                "not completing medication course",
            ],
            resolve_if=[
                "completed full medication course",
                "no fever for 5 days",
                "energy gradually returning",
            ],
        ),
    },
)

# ---------------------------------------------------------------------------
# TB (Tuberculosis)
# ---------------------------------------------------------------------------

TB_TEMPLATE = MonitoringTemplate(
    name="tb_monitoring",
    day_offsets=[7, 14, 30, 60, 90],
    checkpoints={
        7: CheckpointTemplate(
            day_offset=7,
            questions_en=[
                "Are you attending the DOTS center daily and taking all 4 ATT medications?",
                "Any nausea or vomiting from the medications?",
                "Note: yellow or orange urine is normal from rifampicin — are you aware of this?",
                "Any yellowing of the eyes or skin — this is NOT normal and must be reported?",
            ],
            questions_hi=[
                "Kya aap DOTS center roz ja rahe hain aur charon ATT dawaiyan le rahe hain?",
                "Dawai se ji machalana ya ulti ho rahi hai?",
                "Yaad rahe: peshab ka peela ya narangi hona rifampicin se normal hai — kya aap jante hain?",
                "Kya aankhon ya twacha mein peelaahat aa rahi hai — yeh normal NAHI hai, batayein?",
            ],
            escalate_if=[
                "yellow eyes or skin developing — hepatotoxicity from ATT",
                "severe vomiting and cannot take medications",
                "coughing blood",
            ],
            watch_if=[
                "nausea making medication difficult to take",
                "missing DOTS visits",
            ],
            resolve_if=[
                "attending DOTS regularly",
                "tolerating medications with no serious side effects",
                "symptoms slowly improving",
            ],
        ),
        14: CheckpointTemplate(
            day_offset=14,
            questions_en=[
                "Still attending DOTS center every day without any missed days?",
                "Is the cough reducing compared to when you started treatment?",
                "Any numbness or tingling in hands or feet — pyridoxine deficiency sign?",
                "Any sign of yellowing in eyes?",
            ],
            questions_hi=[
                "Abhi bhi DOTS center roz ja rahe hain bina koi din miss kiye?",
                "Kya khasi jab se dawai shuru ki, tab se kam hui hai?",
                "Haath ya pair mein sunn pan ya jhanjhanahat — vitamin B6 ki kami ka lakshan?",
                "Aankhon mein peelaahat ka koi nishaan?",
            ],
            escalate_if=[
                "jaundice or yellow eyes — stop ATT and go to doctor immediately",
                "cough worsening after 2 weeks of treatment",
                "severe peripheral neuropathy",
            ],
            watch_if=[
                "missing any DOTS visits — defaulter risk",
                "cough same as before with no improvement",
            ],
            resolve_if=[
                "zero missed DOTS visits in 2 weeks",
                "cough reducing",
                "no serious side effects",
            ],
        ),
        30: CheckpointTemplate(
            day_offset=30,
            questions_en=[
                "One month of TB treatment completed — how are you feeling overall?",
                "Is the cough much better or gone?",
                "Has your weight improved — are you eating better?",
                "Any fever or night sweats still?",
            ],
            questions_hi=[
                "TB ka ek mahina ka ilaj poora hua — aap overall kaisa feel kar rahe hain?",
                "Khasi ab bahut behtar hai ya band ho gayi?",
                "Wajan sudhar raha hai — khaana theek se kha pa rahe hain?",
                "Abhi bhi bukhar ya raat mein paseena aa raha hai?",
            ],
            escalate_if=[
                "no improvement after 1 month — possible drug resistance",
                "hepatotoxicity signs at any time",
            ],
            watch_if=[
                "slow response to treatment",
                "ongoing weight loss",
            ],
            resolve_if=[
                "cough clearly better",
                "weight stabilizing or increasing",
                "no fever or night sweats",
            ],
        ),
        60: CheckpointTemplate(
            day_offset=60,
            questions_en=[
                "Two months of intensive ATT completed — still on track?",
                "Has the doctor done a sputum test to check treatment response?",
                "How is your energy and weight compared to when you started?",
                "Any side effects at this point?",
            ],
            questions_hi=[
                "ATT ke 2 mahine complete hue — sab theek chal raha hai?",
                "Doctor ne sputum test karwaya treatment response check karne ke liye?",
                "Jab treatment shuru ki tab se ab energy aur wajan kaisa hai?",
                "Koi side effects abhi bhi hain?",
            ],
            escalate_if=[
                "sputum still positive at 2 months — drug-resistant TB evaluation needed",
                "any new side effects emerging",
            ],
            watch_if=[
                "sputum test not yet done",
                "energy not improving",
            ],
            resolve_if=[
                "sputum converted to negative",
                "weight and energy improving",
                "zero treatment interruptions",
            ],
        ),
        90: CheckpointTemplate(
            day_offset=90,
            questions_en=[
                "Three months on TB treatment — are you feeling significantly better?",
                "Still attending DOTS every day without interruption?",
                "Any new concerns or symptoms to report?",
                "Has the treating doctor reviewed your progress recently?",
            ],
            questions_hi=[
                "TB treatment ke 3 mahine — kya aap kaafi behtar feel kar rahe hain?",
                "Abhi bhi DOTS center bina kisi interruption ke roz ja rahe hain?",
                "Koi nayi chinta ya lakshan batane hain?",
                "Treating doctor ne haal hi mein aapki progress dekhi?",
            ],
            escalate_if=[
                "any treatment interruption — re-initiation needed",
                "worsening symptoms at 3 months",
            ],
            watch_if=[
                "adherence becoming difficult",
                "social support issues affecting DOTS attendance",
            ],
            resolve_if=[
                "uninterrupted treatment for 3 months",
                "significant clinical improvement",
                "doctor confirmed good progress",
            ],
        ),
    },
)

# ---------------------------------------------------------------------------
# GENERAL (default fallback)
# ---------------------------------------------------------------------------

GENERAL_TEMPLATE = MonitoringTemplate(
    name="general_monitoring",
    day_offsets=[3, 7, 14],
    checkpoints={
        3: CheckpointTemplate(
            day_offset=3,
            questions_en=[
                "Are you feeling better than when we last spoke?",
                "Are you taking any prescribed medications correctly?",
                "Any new symptoms developing?",
                "Are you eating and drinking normally?",
            ],
            questions_hi=[
                "Pichli baar se ab behtar feel ho raha hai?",
                "Jo dawai di gayi hai, kya sahi tarah se le rahe hain?",
                "Koi naya lakshan aa raha hai?",
                "Khana-pina theek se ho raha hai?",
            ],
            escalate_if=[
                "condition significantly worsening",
                "new serious symptoms developing",
                "unable to take medications",
            ],
            watch_if=[
                "not improving as expected",
                "medication compliance issues",
            ],
            resolve_if=[
                "clearly improving",
                "taking medications correctly",
                "eating and drinking well",
            ],
        ),
        7: CheckpointTemplate(
            day_offset=7,
            questions_en=[
                "How are you feeling at one week?",
                "Main symptoms — are they better, same, or worse?",
                "Any concerns or questions for the doctor?",
                "Do you need to come in for a follow-up?",
            ],
            questions_hi=[
                "Ek hafte mein kaisa feel ho raha hai?",
                "Mukhya lakshan — behtar hain, same hain, ya badh gaye?",
                "Doctor ke liye koi sawaal ya chinta?",
                "Kya aapko dobara aana chahiye follow-up ke liye?",
            ],
            escalate_if=[
                "symptoms worsening at day 7",
                "new symptoms requiring urgent attention",
            ],
            watch_if=[
                "slow recovery",
                "persistent symptoms at 1 week",
            ],
            resolve_if=[
                "significant improvement noted",
                "no new concerns",
                "patient feeling confident about recovery",
            ],
        ),
        14: CheckpointTemplate(
            day_offset=14,
            questions_en=[
                "Two weeks on — are you fully or mostly recovered?",
                "Any symptoms that are still bothering you?",
                "Back to normal activities?",
            ],
            questions_hi=[
                "Do hafte ho gaye — kya aap poori tarah ya zyaadatar theek ho gaye?",
                "Koi takleef jo abhi bhi pareshan kar rahi hai?",
                "Normal kaam par wapas aa gaye?",
            ],
            escalate_if=[
                "not recovered at all at 2 weeks — needs re-evaluation",
            ],
            watch_if=[
                "partial recovery only",
            ],
            resolve_if=[
                "mostly or fully recovered",
                "back to normal routine",
            ],
        ),
    },
)

# ---------------------------------------------------------------------------
# HIGH-RISK IMMEDIATE CHECKPOINT (day 0 — same day, prepended for high/critical)
# ---------------------------------------------------------------------------

HIGH_RISK_IMMEDIATE_CHECKPOINT = CheckpointTemplate(
    day_offset=0,
    questions_en=[
        "Are you safe right now?",
        "Do you need emergency medical help immediately?",
        "Is there someone with you who can help?",
    ],
    questions_hi=[
        "Kya aap abhi surakshit hain?",
        "Kya aapko abhi emergency help chahiye?",
        "Kya koi aapke saath hai jo madad kar sake?",
    ],
    escalate_if=[
        "needs emergency help immediately",
        "alone and in critical condition",
        "unconscious or cannot respond clearly",
    ],
    watch_if=[],
    resolve_if=[
        "patient confirmed safe",
        "emergency services notified if needed",
    ],
)

# ===========================================================================
# TEMPLATE MATCHING
# ===========================================================================


def match_template(
    differentials: list[dict], diagnosis_context: str
) -> MonitoringTemplate:
    """Select the most appropriate monitoring template for this clinical picture."""
    primary = (
        differentials[0].get("diagnosis", "").lower()
        if differentials
        else diagnosis_context.lower()
    )

    if "dengue" in primary:
        return DENGUE_TEMPLATE
    if "typhoid" in primary or "enteric" in primary:
        return TYPHOID_TEMPLATE
    if "malaria" in primary or "plasmodium" in primary:
        return MALARIA_TEMPLATE
    if "tuberculosis" in primary or " tb " in primary or primary.startswith("tb ") or primary == "tb":
        return TB_TEMPLATE
    if any(k in primary for k in ("viral", "influenza", "uri", "upper respiratory")):
        return VIRAL_FEVER_TEMPLATE
    return GENERAL_TEMPLATE


# ===========================================================================
# CHECKPOINT BUILDER
# ===========================================================================


def _build_checkpoint(
    template: CheckpointTemplate,
    language: str,
    base_date: datetime,
) -> Checkpoint:
    """Convert a CheckpointTemplate into a Checkpoint Pydantic model."""
    use_hindi = language.lower() in ("hi", "hinglish")
    questions = template.questions_hi if use_hindi else template.questions_en
    scheduled = (base_date + timedelta(days=template.day_offset)).date()

    return Checkpoint(
        day_offset=template.day_offset,
        scheduled_date=scheduled,
        questions=questions,
        risk_conditions=CheckpointRiskConditions(
            escalate_if=template.escalate_if,
            watch_if=template.watch_if,
            resolve_if=template.resolve_if,
        ),
        status="pending",
        whatsapp_message_id=None,
        patient_response=None,
        response_received_at=None,
        agent_evaluation=None,
    )


# ===========================================================================
# MAIN TOOL FUNCTION
# ===========================================================================


async def write_monitoring_plan(inputs: dict) -> dict:
    """
    Generate a disease-specific monitoring plan and persist it to Supabase.

    Selects a template based on the primary differential, builds dated
    Checkpoint objects in the patient's language, optionally prepends a
    same-day high-risk checkpoint, then writes the plan to Supabase.
    Returns the full plan payload regardless of DB success.
    """
    case_id_str: str = inputs.get("case_id", "")
    diagnosis_context: str = inputs.get("diagnosis_context", "")
    risk_tier: str = inputs.get("risk_tier", "low")
    differentials: list[dict] = inputs.get("differentials", [])
    patient_language: str = inputs.get("patient_language", "en")

    logger.info(
        "write_monitoring_plan | case=%s | risk=%s | language=%s | differentials=%d",
        case_id_str, risk_tier, patient_language, len(differentials),
    )

    base_date = datetime.now(tz=timezone.utc)
    template = match_template(differentials, diagnosis_context)
    logger.info("Template selected: %s", template.name)

    # Build checkpoints
    checkpoints: list[Checkpoint] = []

    if risk_tier in ("high", "critical"):
        checkpoints.append(
            _build_checkpoint(HIGH_RISK_IMMEDIATE_CHECKPOINT, patient_language, base_date)
        )
        logger.info("High-risk immediate checkpoint prepended (day 0)")

    for day_offset in template.day_offsets:
        cp_template = template.checkpoints[day_offset]
        checkpoints.append(_build_checkpoint(cp_template, patient_language, base_date))

    # Build MonitoringPlan model
    try:
        case_uuid = UUID(case_id_str)
    except (ValueError, AttributeError):
        logger.error("write_monitoring_plan: invalid case_id %r", case_id_str)
        return _error_payload(template, checkpoints, "invalid_case_id")

    plan = MonitoringPlan(
        case_id=case_uuid,
        status="active",
        diagnosis_context=diagnosis_context,
        checkpoints=checkpoints,
    )

    # Persist to Supabase
    saved_to_db = False
    saved_plan_id: str | None = None

    try:
        saved = await create_monitoring_plan(plan)
        saved_plan_id = str(saved.plan_id) if saved.plan_id else None
        saved_to_db = True
        logger.info(
            "write_monitoring_plan: saved to DB | plan_id=%s | checkpoints=%d",
            saved_plan_id, len(checkpoints),
        )

        # Write timeline event after monitoring plan is persisted.
        primary_disease = (
            differentials[0].get("diagnosis", diagnosis_context)
            if differentials else diagnosis_context
        )
        await _tl_write(
            case_id    = case_id_str,
            event_type = "monitoring_created",
            payload    = {
                "protocol_name":      template.name,
                "total_checkpoints":  len(checkpoints),
                "duration_days":      max(template.day_offsets) if template.day_offsets else 0,
                "disease":            primary_disease,
            },
            agent_name = "MonitoringPlanWriter",
        )

    except Exception:
        logger.exception(
            "write_monitoring_plan: Supabase save failed for case_id=%s — returning plan without DB id",
            case_id_str,
        )

    first_cp = checkpoints[0]
    total_days = max(template.day_offsets) if template.day_offsets else 0

    return {
        "plan_id": saved_plan_id,
        "template_used": template.name,
        "checkpoints": [cp.model_dump(mode="json") for cp in checkpoints],
        "total_days": total_days,
        "first_checkpoint_date": str(first_cp.scheduled_date),
        "checkpoint_count": len(checkpoints),
        "saved_to_db": saved_to_db,
    }


def _error_payload(
    template: MonitoringTemplate, checkpoints: list[Checkpoint], error: str
) -> dict:
    """Return a partial payload when we cannot proceed to DB save."""
    total_days = max(template.day_offsets) if template.day_offsets else 0
    return {
        "plan_id": None,
        "template_used": template.name,
        "checkpoints": [cp.model_dump(mode="json") for cp in checkpoints],
        "total_days": total_days,
        "first_checkpoint_date": str(checkpoints[0].scheduled_date) if checkpoints else "",
        "checkpoint_count": len(checkpoints),
        "saved_to_db": False,
        "error": error,
    }


# ===========================================================================
# REGISTRY REGISTRATION
# ===========================================================================

from agents.tool_registry import REGISTRY, Tool  # noqa: E402 — after all tool code

REGISTRY.register(
    Tool(
        name="monitoring_plan_writer",
        description="Generate a monitoring plan with checkpoints after a consultation synthesis",
        input_schema={
            "type": "object",
            "properties": {
                "case_id":           {"type": "string"},
                "diagnosis_context": {"type": "string"},
                "risk_tier":         {"type": "string"},
                "differentials":     {"type": "array"},
                "patient_language":  {"type": "string"},
            },
            "required": ["case_id", "diagnosis_context", "risk_tier"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "plan_id":               {"type": "string"},
                "template_used":         {"type": "string"},
                "checkpoints":           {"type": "array"},
                "total_days":            {"type": "integer"},
                "first_checkpoint_date": {"type": "string"},
                "checkpoint_count":      {"type": "integer"},
                "saved_to_db":           {"type": "boolean"},
            },
        },
        agent="case_manager_agent",
        async_fn=write_monitoring_plan,
    )
)

logger.debug("monitoring_plan_writer: real implementation registered")
