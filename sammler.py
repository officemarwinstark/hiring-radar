"""Hiring-Radar, Sammler (Fassung 2).
Liest offene Stellen aus oeffentlichen Greenhouse-Listen, ordnet Land und Bereich zu
und baut daraus data/stellen.json, data/bericht.json und die Seite docs/index.html."""
import json
import os
import re
import urllib.request
from datetime import datetime, timezone

QUELLE = "https://boards-api.greenhouse.io/v1/boards/{}/jobs"

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
    with open("firmen.txt", encoding="utf-8") as datei:
        zeilen = [zeile.strip().lower() for zeile in datei]
    firmen = []
    for z in zeilen:
        if z and not z.startswith("#") and z not in firmen:
            firmen.append(z)
    return firmen


def hole_stellen(kuerzel):
    anfrage = urllib.request.Request(QUELLE.format(kuerzel), headers={"User-Agent": "hiring-radar"})
    with urllib.request.urlopen(anfrage, timeout=30) as antwort:
        return json.load(antwort).get("jobs", [])


def tage_seit(datum_text, heute):
    try:
        return max((heute - datetime.fromisoformat(datum_text)).days, 0)
    except (TypeError, ValueError):
        return None


def sammle(heute):
    stellen, bericht = [], []
    for kuerzel in lade_firmen():
        try:
            jobs = hole_stellen(kuerzel)
        except Exception as grund:  # eine kaputte Firma stoppt nicht den Rest
            bericht.append({"kuerzel": kuerzel, "stellen": 0, "dach": 0, "fehler": str(grund)[:80]})
            continue
        eigene = []
        for job in jobs:
            erstmals = job.get("first_published") or job.get("updated_at")
            ort = (job.get("location") or {}).get("name") or ""
            titel = (job.get("title") or "").strip()
            eigene.append({
                "firma": (job.get("company_name") or kuerzel).strip(),
                "titel": titel,
                "ort": ort.strip(),
                "land": land_von(ort),
                "bereich": bereich_von(titel),
                "online_seit": (erstmals or "")[:10],
                "tage_offen": tage_seit(erstmals, heute),
                "link": job.get("absolute_url") or "",
            })
        bericht.append({
            "kuerzel": kuerzel,
            "name": eigene[0]["firma"] if eigene else "",
            "stellen": len(eigene),
            "dach": sum(1 for s in eigene if s["land"] != "Ausland"),
        })
        stellen.extend(eigene)
    stellen.sort(key=lambda s: -(s["tage_offen"] or 0))
    return stellen, bericht


def baue_seite(stellen, heute):
    with open("seite.html", encoding="utf-8") as datei:
        vorlage = datei.read()
    daten = {
        "stand": f"{heute:%d.%m.%Y}",
        "stellen": [
            [s["firma"], s["titel"], s["ort"], s["land"], s["bereich"], s["tage_offen"],
             s["link"] if s["link"].startswith("https://") else ""]
            for s in stellen
        ],
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
    print(f"{len(stellen)} Stellen bei {len(ok)} Firmen gespeichert.")
    for b in bericht:
        if "fehler" in b:
            print("Nicht erreichbar:", b["kuerzel"], "-", b["fehler"])
    if not stellen:
        raise SystemExit("Keine einzige Stelle gefunden. Bitte firmen.txt pruefen.")


if __name__ == "__main__":
    main()
