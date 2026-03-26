from datetime import date, timedelta

CTL_DAYS = 42  # Chronic Training Load — 42-Tage EMA
ATL_DAYS = 7   # Acute Training Load  —  7-Tage EMA


def calculate_pmc(
    daily_tss: dict[str, float],
    start_date: date,
    end_date: date,
) -> list[dict]:
    """
    Berechnet CTL (Fitness), ATL (Fatigue) und TSB (Form) für jeden Tag.

    daily_tss: dict von ISO-Datum → TSS-Wert (Tage ohne Eintrag = 0)
    start_date / end_date: inklusiver Bereich

    Morning Values: TSB[t] = CTL[t-1] - ATL[t-1]
    CTL = {CTL_DAYS}-Tage exponentieller Durchschnitt
    ATL = {ATL_DAYS}-Tage exponentieller Durchschnitt
    """
    result = []
    ctl = 0.0
    atl = 0.0
    current = start_date

    while current <= end_date:
        date_str = current.isoformat()
        tss = daily_tss.get(date_str, 0.0)

        # Morning Value: Form BEVOR der heutige Tag trainiert wird
        tsb = ctl - atl

        # EMA-Update
        ctl = ctl + (tss - ctl) / CTL_DAYS
        atl = atl + (tss - atl) / ATL_DAYS

        result.append({
            "date": date_str,
            "tss": tss,
            "ctl": round(ctl, 1),
            "atl": round(atl, 1),
            "tsb": round(tsb, 1),
        })
        current += timedelta(days=1)

    return result
