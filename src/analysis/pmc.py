from datetime import date, timedelta


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
    CTL = 42-Tage exponentieller Durchschnitt
    ATL = 7-Tage exponentieller Durchschnitt
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
        ctl = ctl + (tss - ctl) / 42
        atl = atl + (tss - atl) / 7

        result.append({
            "date": date_str,
            "tss": tss,
            "ctl": round(ctl, 1),
            "atl": round(atl, 1),
            "tsb": round(tsb, 1),
        })
        current += timedelta(days=1)

    return result
