import logging
from datetime import date
from openai import OpenAI

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
Du bist ein professioneller Rad- und Gesundheitscoach. \
Du kennst die Gesundheitsdaten und Trainingshistorie der letzten {days} Tage.
Heute ist {today}.
Analysiere die Daten und gib eine konkrete, persönliche Tagesempfehlung.
Sei direkt, motivierend und präzise. Strukturiere deine Antwort in maximal 3 kurze Absätze:
1. Aktuelle Erholungslage bewerten
2. Konkrete Empfehlung für heute
3. Hinweis auf kommende Rennen oder wichtige Trends (falls relevant)"""


def build_prompt(blocks: dict, today: str, days: int) -> str:
    lines = [f"=== Trainingstagebuch (letzte {days} Tage) ===\n"]

    for day in reversed(blocks["daily"]):
        line = (
            f"[{day.get('date','?')}] "
            f"Schlaf: {day.get('sleep_score','?')}, "
            f"BB: {day.get('body_battery','?')}, "
            f"HRV: {day.get('hrv_status','?')}, "
            f"Stress: {day.get('stress_total','?')}, "
            f"Readiness: {day.get('readiness_score','?')}"
        )
        lines.append(line)

    if blocks["activities"]:
        lines.append("\n=== Aktivitäten ===")
        for act in blocks["activities"][:10]:
            lines.append(
                f"[{act.get('date','?')}] {act.get('activity_type','?')} "
                f"{act.get('distance_km','?')}km "
                f"NP:{act.get('norm_power','?')}W "
                f"TSS:{act.get('tss','?')}"
            )

    if blocks["events"]:
        lines.append("\n=== Kommende Events ===")
        for ev in blocks["events"]:
            lines.append(
                f"[{ev.get('date_start','?')}] {ev.get('title','?')} "
                f"({ev.get('event_type','?')}, Prio: {ev.get('priority','?')})"
            )

    if blocks["personal_records"]:
        lines.append("\n=== Persönliche Bestleistungen ===")
        for pr in blocks["personal_records"]:
            lines.append(
                f"{pr.get('activity_type','?')} / {pr.get('category','?')}: "
                f"{pr.get('value','?')} ({pr.get('date','?')})"
            )

    if blocks.get("blood_pressure"):
        lines.append("\n=== Blutdruck (letzte Messungen) ===")
        for bp in blocks["blood_pressure"][:5]:
            lines.append(
                f"{bp.get('measured_at','?')}: "
                f"{bp.get('systolic','?')}/{bp.get('diastolic','?')} "
                f"{bp.get('pulse','?')}bpm"
            )

    return "\n".join(lines)


def run_gpt_analysis(
    api_key: str,
    model: str,
    blocks: dict,
    max_tokens: int = 1000,
    temperature: float = 0.4,
    days: int = 14,
) -> str:
    """
    Synchrone GPT-Analyse — via asyncio.to_thread aufrufen.
    Wirft Exception bei API-Fehler (Aufrufer kümmert sich um Fallback).
    """
    today = date.today().strftime("%A, %d. %B %Y")
    prompt = build_prompt(blocks, today, days)

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": _SYSTEM_PROMPT.format(days=days, today=today),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content
