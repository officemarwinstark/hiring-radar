"""Hiring-Radar, Sammler (Fassung 3).
Liest offene Stellen aus den oeffentlichen Stellenlisten von Greenhouse, Ashby und Lever,
behaelt die Stellen im deutschsprachigen Raum, ordnet Land und Bereich zu
und baut daraus data/stellen.json, data/bericht.json und die Seite docs/index.html."""
import json
import os
import re
import urllib.request
from datetime import datetime, timezone

ADRESSEN = {
    "greenhouse": ["https://boards-api.greenhouse.io/v1/boards/{}/jobs"],
    "ashby": ["https://api.ashbyhq.com/posting-api/job-board/{}"],
    "lever": ["https://api.lever.co/v0/postings/{}?mode=json", "https://api.eu.lever.co/v0/postings/{}?mode=json"],
}
LAND_KUERZEL = {"DE": "Deutschland", "AT": "Österreich", "CH": "Schweiz"}

LAND_WORTE = {
    "Deutschland": ["germany", "deutschland"],
    "Österreich": ["austria", "österreich", "oesterreich"],
    "Schweiz": ["switzerland", "schweiz"],
}
AUSLAND_WORTE = [
    "united states", "usa", "u.s.", "united kingdom", "uk", "england", "france", "spain", "italy",
    "netherlands", "belgium", "poland", "portugal", "ireland", "sweden", "denmark", "norway",
    "finland", "bulgaria", "romania", "greece", "turkey", "india", "china", "japan", "singapore",
    "australia", "canada", "mexico", "brazil", "brasil", "chile", "colombia", "argentina",
    "israel", "estonia", "lithuania", "latvia", "czech", "hungary", "serbia", "croatia", "ukraine",
    "philippines", "new zealand", "south africa", "luxembourg", "korea", "uae", "emirates",
]
STADT_WORTE = {
    "Deutschland": [
        "berlin", "munich", "münchen", "muenchen", "hamburg", "cologne", "köln", "koeln", "frankfurt",
        "stuttgart", "düsseldorf", "duesseldorf", "dusseldorf", "leipzig", "dresden", "hannover",
        "nuremberg", "nürnberg", "bremen", "essen", "dortmund", "bonn", "karlsruhe", "mannheim",
        "münster", "potsdam", "heidelberg", "darmstadt", "aachen", "freiburg", "augsburg", "kiel",
        "rostock", "regensburg", "wolfsburg", "walldorf", "verden", "barleben", "magdeburg", "erfurt",
        "jena", "bielefeld", "bochum", "wuppertal", "mainz", "wiesbaden", "ulm", "ingolstadt",
        "paderborn", "saarbrücken",
    ],
    "Österreich": ["vienna", "wien", "graz", "linz", "salzburg", "innsbruck", "klagenfurt"],
    "Schweiz": [
        "zurich", "zürich", "geneva", "genf", "genève", "basel", "bern", "lausanne", "zug",
        "lugano", "winterthur", "luzern", "lucerne", "st. gallen",
    ],
}
BEREICHE = [
    ("Sales", r"sales|account executive|account manager|business development|vertrieb|\bsdr\b|\bbdr\b|key account|partner manager|partnerships"),
    ("Kundenservice", r"customer success|customer support|customer service|customer care|customer experience|kundenservice|kundenbetreuung|support specialist|support agent"),
    ("Marketing", r"marketing|brand|content|\bseo\b|\bcrm\b|growth|communications|\bpr\b|social media|campaign"),
    ("Daten", r"\bdata\b|analytics|analyst|scientist|machine learning|\bml\b|\bai\b|\bbi\b"),
    ("Technik", r"engineer|developer|entwickler|software|devops|\bsre\b|architect|backend|frontend|full.?stack|\bqa\b|security|\bit\b|infrastructure|platform"),
    ("Produkt und Design", r"product manager|product owner|product lead|head of product|designer|\bux\b|\bui\b|researcher|product design"),
    ("Finanzen und Recht", r"finance|financial|accounting|accountant|controller|controlling|legal|counsel|\btax\b|treasury|compliance|\brisk\b|audit|buchhalt|payroll|\baml\b|\bafc\b|fraud"),
    ("Personal", r"recruit|talent|people|\bhr\b|human resources|personal"),
    ("Betrieb und Logistik", r"operations|logistics|logistik|supply chain|warehouse|lager|produktion|production|fulfil|driver|fahrer|\bchef\b|koch|procurement|einkauf|maintenance|quality|planner|planning"),
]
BEREICHE = [(name, re.compile(muster)) for name, muster in BEREICHE]


def wort_drin(text, worte):
    return any(re.search(r"(?<![a-zäöüß])" + re.escape(w) + r"(?![a-zäöüß])", text) for w in worte)


def land_von(ort):
    text = (ort or "").lower()
    for land, worte in LAND_WORTE.items():
        if wort_drin(text, worte):
            return land
    if wort_drin(text, AUSLAND_WORTE):
        return "Ausland"
    for land, worte in STADT_WORTE.items():
        if wort_drin(text, worte):
            return land
    return "Ausland"


def bereich_von(titel):
    text = (titel or "").lower()
    for name, muster in BEREICHE:
        if muster.search(text):
            return name
    return "Sonstiges"


def lade_firmen():
    """Zeilenformat: [quelle:]kuerzel [| Anzeigename]. Ohne Quelle gilt greenhouse."""
    firmen, gesehen = [], set()
    with open("firmen.txt", encoding="utf-8") as datei:
        for zeile in datei:
            zeile = zeile.strip()
            if not zeile or zeile.startswith("#"):
                continue
            eintrag, _, name = zeile.partition("|")
            quelle, _, kuerzel = eintrag.strip().rpartition(":")
            quelle = (quelle or "greenhouse").strip().lower()
            kuerzel = kuerzel.strip()
            if quelle not in ADRESSEN or not kuerzel or (quelle, kuerzel.lower()) in gesehen:
                continue
            gesehen.add((quelle, kuerzel.lower()))
            firmen.append({"quelle": quelle, "kuerzel": kuerzel, "name": name.strip()})
    return firmen


def hole_json(adresse):
    anfrage = urllib.request.Request(adresse, headers={"User-Agent": "hiring-radar"})
    with urllib.request.urlopen(anfrage, timeout=40) as antwort:
        return json.load(antwort)


def hole_roh(quelle, kuerzel):
    """Probiert die Adressen der Quelle der Reihe nach und gibt die erste Antwort zurueck."""
    letzter = None
    for muster in ADRESSEN[quelle]:
        try:
            return hole_json(muster.format(kuerzel))
        except Exception as grund:
            letzter = grund
    raise letzter


def datum_von(wert):
    """Macht aus einem Datumstext oder Millisekunden-Wert ein Datum, sonst None."""
    try:
        if isinstance(wert, (int, float)):
            return datetime.fromtimestamp(wert / 1000, tz=timezone.utc)
        d = datetime.fromisoformat(wert)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def dach_ort(orte, laender=()):
    """Sucht unter mehreren Orten den ersten im deutschsprachigen Raum."""
    for kuerzel in laender:
        if kuerzel in LAND_KUERZEL and orte:
            return orte[0], LAND_KUERZEL[kuerzel]
    for ort in orte:
        land = land_von(ort)
        if land != "Ausland":
            return ort, land
    return (orte[0] if orte else ""), "Ausland"


def lese_greenhouse(roh, firma):
    for job in roh.get("jobs", []):
        ort = ((job.get("location") or {}).get("name") or "").strip()
        yield {
            "firma": (job.get("company_name") or firma["name"] or firma["kuerzel"]).strip(),
            "titel": job.get("title"), "orte": [ort], "laender": (),
            "erstmals": datum_von(job.get("first_published") or job.get("updated_at")),
            "link": job.get("absolute_url"),
        }


def lese_ashby(roh, firma):
    for job in roh.get("jobs", []):
        if job.get("isListed") is False:
            continue
        orte = []
        for stelle in [job] + list(job.get("secondaryLocations") or []):
            ort = (stelle.get("location") or "").strip()
            adresse = ((stelle.get("address") or {}).get("postalAddress") or stelle.get("postalAddress") or {})
            land = (adresse.get("addressCountry") or "").strip()
            if land and land.lower() not in ort.lower():
                ort = f"{ort}, {land}" if ort else land
            if ort:
                orte.append(ort)
        yield {
            "firma": firma["name"] or firma["kuerzel"], "titel": job.get("title"), "orte": orte, "laender": (),
            "erstmals": datum_von(job.get("publishedAt")), "link": job.get("jobUrl"),
        }


def lese_lever(roh, firma):
    for job in roh if isinstance(roh, list) else []:
        kat = job.get("categories") or {}
        orte = [o for o in [kat.get("location")] + list(kat.get("allLocations") or []) if o]
        yield {
            "firma": firma["name"] or firma["kuerzel"], "titel": job.get("text"), "orte": orte,
            "laender": ((job.get("country") or "").upper(),),
            "erstmals": datum_von(job.get("createdAt")), "link": job.get("hostedUrl"),
        }


LESER = {"greenhouse": lese_greenhouse, "ashby": lese_ashby, "lever": lese_lever}


def sammle(heute):
    stellen, bericht = [], []
    for firma in lade_firmen():
        eintrag = {"quelle": firma["quelle"], "kuerzel": firma["kuerzel"]}
        try:
            roh = hole_roh(firma["quelle"], firma["kuerzel"])
            jobs = list(LESER[firma["quelle"]](roh, firma))
        except Exception as grund:  # eine kaputte Firma stoppt nicht den Rest
            eintrag.update(stellen=0, dach=0, fehler=str(grund)[:80])
            bericht.append(eintrag)
            continue
        eigene = []
        for job in jobs:
            ort, land = dach_ort(job["orte"], job["laender"])
            if land == "Ausland":
                continue
            titel = (job["titel"] or "").strip()
            link = job["link"] or ""
            eigene.append({
                "firma": job["firma"], "titel": titel, "ort": ort, "land": land,
                "bereich": bereich_von(titel),
                "online_seit": f"{job['erstmals']:%Y-%m-%d}" if job["erstmals"] else "",
                "tage_offen": max((heute - job["erstmals"]).days, 0) if job["erstmals"] else None,
                "link": link if link.startswith("https://") else "",
            })
        eintrag.update(name=(jobs[0]["firma"] if jobs else firma["name"]), stellen=len(jobs), dach=len(eigene))
        bericht.append(eintrag)
        stellen.extend(eigene)
    stellen.sort(key=lambda s: -(s["tage_offen"] or 0))
    return stellen, bericht


def baue_seite(stellen, heute):
    with open("seite.html", encoding="utf-8") as datei:
        vorlage = datei.read()
    daten = {
        "stand": f"{heute:%d.%m.%Y}",
        "stellen": [[s["firma"], s["titel"], s["ort"], s["land"], s["bereich"], s["tage_offen"], s["link"]] for s in stellen],
    }
    text = json.dumps(daten, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    if "__DATEN__" not in vorlage:
        raise SystemExit("In seite.html fehlt der Platzhalter __DATEN__.")
    return vorlage.replace("__DATEN__", text)


def main():
    heute = datetime.now(timezone.utc)
    stellen, bericht = sammle(heute)
    os.makedirs("data", exist_ok=True)
    os.makedirs("docs", exist_ok=True)
    with open("data/stellen.json", "w", encoding="utf-8") as datei:
        json.dump(stellen, datei, ensure_ascii=False, indent=1)
    with open("data/bericht.json", "w", encoding="utf-8") as datei:
        json.dump({"stand": f"{heute:%Y-%m-%d %H:%M}", "firmen": bericht}, datei, ensure_ascii=False, indent=1)
    with open("docs/index.html", "w", encoding="utf-8") as datei:
        datei.write(baue_seite(stellen, heute))
    ok = [b for b in bericht if "fehler" not in b]
    print(f"{len(stellen)} Stellen im deutschsprachigen Raum bei {len(ok)} erreichbaren Firmen gespeichert.")
    for b in bericht:
        if "fehler" in b:
            print("Nicht erreichbar:", b["quelle"], b["kuerzel"], "-", b["fehler"])
    if not stellen:
        raise SystemExit("Keine einzige Stelle gefunden. Bitte firmen.txt pruefen.")


if __name__ == "__main__":
    main()
