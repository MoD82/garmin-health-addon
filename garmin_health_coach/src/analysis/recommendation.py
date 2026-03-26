def _recovery_score(
    readiness: int | None,
    body_battery: int | None,
    hrv_status: str | None,
) -> int:
    """
    Composite Recovery Score (0–100).
    Basis: readiness > body_battery > 60 (Default)
    HRV-Strafen: POOR = -20, UNBALANCED = -10
    """
    if readiness is not None:
        base = readiness
    elif body_battery is not None:
        base = body_battery
    else:
        base = 60

    if hrv_status == "POOR":
        base -= 20
    elif hrv_status == "UNBALANCED":
        base -= 10

    return max(0, min(100, base))


def get_recommendation(
    tsb: float,
    readiness: int | None,
    body_battery: int | None,
    hrv_status: str | None,
) -> dict:
    """
    8-stufige Trainingsempfehlung basierend auf TSB (Form) und Recovery Score.

    Gibt zurück: emoji, title, reason, color, recovery_score
    """
    rec = _recovery_score(readiness, body_battery, hrv_status)

    # Schritt 1: Recovery-basierte Sicherheitsprüfung
    if rec < 35:
        return {
            "emoji": "🛑",
            "title": "Pause",
            "reason": (
                "Dein Körper signalisiert echte Erschöpfung. "
                "Training heute würde mehr schaden als nützen. "
                "Schlaf, Essen, Ruhe — das ist heute das Training."
            ),
            "color": "#e74c3c",
            "recovery_score": rec,
        }

    # Schritt 2: TSB + Recovery kombiniert
    if tsb < -20 or rec < 50:
        return {
            "emoji": "🚶",
            "title": "Aktive Regeneration",
            "reason": (
                "Du trägst gerade viel Trainingsbelastung mit dir. "
                "Ein lockerer Spaziergang oder 30 min ruhiges Radeln "
                "fördert die Erholung besser als ein weiterer harter Tag."
            ),
            "color": "#e67e22",
            "recovery_score": rec,
        }

    # TSB-Grenzen: tsb<-5 = Stufe 3, tsb∈[-5,5] = Stufe 4 (beide Grenzen inklusiv für Stufe 4)
    if tsb < -5:
        return {
            "emoji": "🚴",
            "title": "Grundlage Z2",
            "reason": (
                "Du bist noch im Aufbau — das ist gut! "
                "Heute passt lockeres Grundlagentraining: "
                "Herzfrequenz niedrig halten, Technik pflegen, Ausdauer aufbauen."
            ),
            "color": "#f39c12",
            "recovery_score": rec,
        }

    if tsb <= 5:
        return {
            "emoji": "💪",
            "title": "Kraft oder Z2",
            "reason": (
                "Gute Balance zwischen Belastung und Erholung. "
                "Krafttraining im Studio oder ein solides Z2-Intervall "
                "baut jetzt Fitness auf ohne dich zu überlasten."
            ),
            "color": "#27ae60",
            "recovery_score": rec,
        }

    # TSB > 5 ab hier
    if rec < 70:
        return {
            "emoji": "🚴",
            "title": "Grundlage Z2",
            "reason": (
                "Deine Form ist gut, aber der Körper ist noch nicht ganz frisch. "
                "Nutze den Tag für lockeres Grundlagentraining — "
                "so baust du Fitness auf ohne die Erholung zu gefährden."
            ),
            "color": "#f39c12",
            "recovery_score": rec,
        }

    if tsb <= 20:
        return {
            "emoji": "⚡",
            "title": "Schwellentraining",
            "reason": (
                "Du bist ausgeruht und deine Form passt. "
                "Jetzt kannst du Gas geben: Schwellenintervalle (Z4) "
                "verbessern direkt deine Wettkampfleistung."
            ),
            "color": "#2980b9",
            "recovery_score": rec,
        }

    # TSB > 20
    if rec < 85:
        return {
            "emoji": "🔥",
            "title": "VO2max-Training",
            "reason": (
                "Sehr gute Form! Kurze, intensive Intervalle (Z5/VO2max) "
                "bringen jetzt den größten Trainingseffekt. "
                "Halte die Einheit kurz und knackig."
            ),
            "color": "#8e44ad",
            "recovery_score": rec,
        }

    return {
        "emoji": "🏆",
        "title": "Wettkampfbereit",
        "reason": (
            "Topform! Du bist ausgeruht, fit und bereit für Höchstleistung. "
            "Wenn kein Rennen ansteht: ein kurzes, intensives Test-Effort "
            "oder genieße einfach wie gut sich das Fahren anfühlt."
        ),
        "color": "#c0392b",
        "recovery_score": rec,
    }
