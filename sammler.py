"""Hiring-Radar, Sammler (Fassung 4).
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
    ("Sales", r"sales|account executive|account manager|account director|account partner|business development|vertrieb|\bsdr\b|\bbdr\b|key account|partner manager|partnerships|pre.?sales|solutions? engineer|solutions? consultant|außendienst|aussendienst|innendienst|verkäufer|verkauf|revenue|customer advisor|kundenberater|kundenmanager|partner development|account management|commercial|\bgtm\b|go.to.market|enablement"),
    ("Kundenservice", r"customer success|customer support|customer service|customer care|customer experience|kundenservice|kundenbetreuung|support specialist|support agent|support engineer|technical support|onboarding|implementation|kundenbetreu|customer education|client experience|\bcustomer\b"),
    ("Marketing", r"marketing|brand|content|\bseo\b|\bcrm\b|growth|communications|kommunikation|\bpr\b|social media|campaign|creator|community|events?\b|copywriter|redakt|media buyer|\bpaid\b|\bsea\b|acquisit|performance"),
    ("Handwerk und Montage", r"monteur|elektriker|elektroniker|elektrofach|installateur|handwerk|dachdecker|mechatroniker|montage|bauleiter|techniker|technician|anlagenmechaniker|servicetechniker|obermonteur|gerüst|zimmer(er|mann)|solarteur"),
    ("Hardware und Ingenieurwesen", r"mechanical|electrical|electronics|embedded|firmware|hardware|avionics|propulsion|manufacturing|structural|structures|thermal|\brf\b|optical|optics|robotics|mechatronic|konstrukt|fertigung|test engineer|systems engineer|\bgnc\b|aerospace|launch|satellite|fpga|\basic\b|battery|chassis|powertrain|fluid|materials|process engineer|production engineer|flight|guidance|verfahrens|entwicklungsingenieur|ingenieur"),
    ("Daten und KI", r"\bdata\b|daten|analytics|analyst|scientist|machine learning|\bml\b|\bai\b|\bki\b|\bbi\b|research engineer|researcher|research scientist|applied ai|forward deployed"),
    ("Software und IT", r"engineer|developer|entwickler|software|devops|\bsre\b|architect|backend|frontend|full.?stack|\bqa\b|security|\bit\b|infrastructure|platform|programmer|administrator|sysadmin|cloud|mobile|android|\bios\b"),
    ("Produkt und Design", r"product manager|product owner|product lead|head of product|produktmanager|designer|\bux\b|\bui\b|product design|product marketing|product operations|\bproduct\b"),
    ("Finanzen und Recht", r"finance|financial|finanz|accounting|accountant|controller|controlling|legal|counsel|jurist|recht|\btax\b|steuer|treasury|compliance|\brisk\b|audit|buchhalt|payroll|\baml\b|\bafc\b|fraud|\bfp&a\b|credit|underwrit|regulatory|datenschutz|privacy|investor relations|financing|compensation|\bm&a\b"),
    ("Personal", r"recruit|talent|people|\bhr\b|human resources|personal|learning|workplace|office manager|feel.?good"),
    ("Strategie und Projekte", r"strategy|strategie|business operations|bizops|chief of staff|founders? associate|project manager|projektmanager|projektleiter|program manager|programme manager|consultant|berater|\bpmo\b|transformation|special projects|general manager|managing director|geschäftsführ|entrepreneur in residence|venture"),
    ("Betrieb und Logistik", r"operations|logistics|logistik|supply chain|warehouse|lager|produktion|production|fulfil|driver|fahrer|\bchef\b|koch|procurement|einkauf|purchas|maintenance|instandhalt|quality|qualität|planner|planning|planung|dispatcher|dispo|facility|reinig|sicherheit|safety|assistant|assistenz|empfang|kommission|picker|packer|schichtleiter|shift|customs|zoll|spedition|lokführer|koordinator|coordinator|inspector|fsqa|\bcnc\b|trainer|food|küche|kitchen"),
]
BEREICHE = [(name, re.compile(muster)) for name, muster in BEREICHE]

STUFEN = ["Praktikum und Werkstudent", "Junior", "Erfahren", "Senior", "Lead und Principal", "Head und Director", "VP und C-Level"]
STUFEN_MUSTER = [
    (0, r"\bintern\b|internship|praktik|werkstudent|working student|\bstudent|azubi|ausbildung|auszubildende|duales studium|dual student|thesis|abschlussarbeit|masterand|bachelorand|aushilfe|minijob|schülerpraktik"),
    (5, r"chief of staff"),
    (6, r"\bvp\b|\bsvp\b|\bevp\b|vice president|chief \w+( \w+){0,2} officer|^\W*(ceo|cfo|cto|coo|cio|cmo|cpo|ciso)\b(?! office)|geschäftsführ|managing director|general manager|country manager|co-?founder"),
    (5, r"\bhead\b|director|\bleiter|leiterin|\bleitung|bereichsleit|abteilungsleit"),
    (4, r"\blead\b(?! gen)|principal|\bstaff\b|team ?lead|teamleit|engineering manager|gruppenleit|schichtleit|bauleit"),
    (3, r"\bsenior\b|\bsr\b|\bexpert\b|experienced"),
    (1, r"\bjunior\b|\bjr\b|associate|entry.?level|graduate|berufseinsteiger|trainee|quereinsteiger"),
]
STUFEN_MUSTER = [(stufe, re.compile(muster)) for stufe, muster in STUFEN_MUSTER]
STUFEN_GEWICHT = [0.5, 1, 2, 3, 4, 5, 6]

ART_TITEL = [
    ("Werkstudent", r"werkstudent|working student"),
    ("Praktikum", r"\bintern\b|internship|praktik|thesis|abschlussarbeit|masterand|bachelorand"),
    ("Ausbildung", r"azubi|ausbildung|auszubildende|duales studium|dual student"),
    ("Freelance", r"freelance|freiberuf|contractor|\bbefristet|temporary|interim"),
    ("Teilzeit", r"teilzeit|part.?time|minijob|aushilfe"),
]
ART_TITEL = [(name, re.compile(muster)) for name, muster in ART_TITEL]
ART_ANGABE = [
    ("Praktikum", r"intern"), ("Werkstudent", r"working student|werkstudent"), ("Teilzeit", r"part"),
    ("Freelance", r"contract|temporary|freelance|befristet"), ("Vollzeit", r"full|vollzeit"),
]
ART_ANGABE = [(name, re.compile(muster)) for name, muster in ART_ANGABE]

STAEDTE = {
    "Berlin": ["berlin"], "München": ["munich", "münchen", "muenchen", "ottobrunn", "garching", "parsdorf"], "Hamburg": ["hamburg"],
    "Köln": ["cologne", "köln", "koeln"], "Frankfurt": ["frankfurt"], "Stuttgart": ["stuttgart", "leonberg"],
    "Düsseldorf": ["düsseldorf", "duesseldorf", "dusseldorf"], "Leipzig": ["leipzig"], "Dresden": ["dresden"],
    "Hannover": ["hannover"], "Nürnberg": ["nuremberg", "nürnberg"], "Bremen": ["bremen"], "Dortmund": ["dortmund"],
    "Bonn": ["bonn"], "Bochum": ["bochum"], "Karlsruhe": ["karlsruhe"], "Mannheim": ["mannheim"], "Heidelberg": ["heidelberg"],
    "Magdeburg": ["magdeburg", "barleben"], "Verden": ["verden"], "Augsburg": ["augsburg"], "Wien": ["vienna", "wien"],
    "Zürich": ["zurich", "zürich"], "Genf": ["geneva", "genf", "genève"], "Basel": ["basel"], "Bern": ["bern"],
}

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


def stufe_von(titel):
    text = (titel or "").lower()
    for stufe, muster in STUFEN_MUSTER:
        if muster.search(text):
            return stufe
    return 2


def art_von(titel, angabe=""):
    text = (titel or "").lower()
    for name, muster in ART_TITEL:
        if muster.search(text):
            return name
    hinweis = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", angabe or "").lower()
    for name, muster in ART_ANGABE:
        if muster.search(hinweis):
            return name
    return ""


def stadt_von(ort):
    text = (ort or "").lower()
    for stadt, worte in STAEDTE.items():
        if wort_drin(text, worte):
            return stadt
    return ""


def modus_von(angabe, ort, remote=None):
    text = re.sub(r"[^a-z]", "", (angabe or "").lower())
    if text == "remote" or (not text and remote is True):
        return "Remote"
    if text == "hybrid":
        return "Hybrid"
    if text in ("onsite", "office"):
        return "Vor Ort"
    if "remote" in (ort or "").lower():
        return "Remote"
    return ""


def druck_von(stufe, tage):
    """0 bis 100: hohe Rolle und lange offen ergibt viel Druck. Ueber 180 Tage gilt als Dauer-Anzeige."""
    if tage is None:
        return 0
    wirksam = tage if tage <= 180 else 20
    return round(100 * STUFEN_GEWICHT[stufe] * wirksam / (STUFEN_GEWICHT[-1] * 180))


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
            "art": " ".join(str(m.get("value")) for m in (job.get("metadata") or [])
                            if isinstance(m, dict) and isinstance(m.get("value"), str)
                            and re.search(r"time type|employment|commitment|contract|anstellung", str(m.get("name")).lower())),
            "modus": "", "remote": None,
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
            "art": job.get("employmentType") or "", "modus": job.get("workplaceType") or "", "remote": job.get("isRemote"),
        }


def lese_lever(roh, firma):
    for job in roh if isinstance(roh, list) else []:
        kat = job.get("categories") or {}
        orte = [o for o in [kat.get("location")] + list(kat.get("allLocations") or []) if o]
        yield {
            "firma": firma["name"] or firma["kuerzel"], "titel": job.get("text"), "orte": orte,
            "laender": ((job.get("country") or "").upper(),),
            "erstmals": datum_von(job.get("createdAt")), "link": job.get("hostedUrl"),
            "art": kat.get("commitment") or "", "modus": job.get("workplaceType") or "", "remote": None,
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
            tage = max((heute - job["erstmals"]).days, 0) if job["erstmals"] else None
            stufe = stufe_von(titel)
            eigene.append({
                "firma": job["firma"], "titel": titel, "ort": ort, "land": land, "stadt": stadt_von(ort),
                "bereich": bereich_von(titel), "stufe": stufe, "art": art_von(titel, job["art"]),
                "modus": modus_von(job["modus"], " ".join(job["orte"]), job["remote"]),
                "online_seit": f"{job['erstmals']:%Y-%m-%d}" if job["erstmals"] else "",
                "tage_offen": tage, "druck": druck_von(stufe, tage),
                "link": link if link.startswith("https://") else "",
            })
        eintrag.update(name=(jobs[0]["firma"] if jobs else firma["name"]), stellen=len(jobs), dach=len(eigene))
        bericht.append(eintrag)
        stellen.extend(eigene)
    stellen.sort(key=lambda s: (-s["druck"], -(s["tage_offen"] or 0)))
    return stellen, bericht


def baue_seite(stellen, heute):
    with open("seite.html", encoding="utf-8") as datei:
        vorlage = datei.read()
    daten = {
        "stand": f"{heute:%d.%m.%Y}",
        "stufen": STUFEN,
        "stellen": [[s["firma"], s["titel"], s["ort"], s["land"], s["bereich"], s["tage_offen"], s["link"],
                     s["stufe"], s["art"], s["stadt"], s["modus"], s["druck"]] for s in stellen],
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
