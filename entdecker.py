"""Hiring-Radar, Entdecker.
Prueft die Firmen aus kandidaten/ats-verzeichnis.csv, die noch nicht in firmen.txt stehen.
Jede Firma mit mindestens einer Stelle im deutschsprachigen Raum wird in firmen.txt aufgenommen.
Das Ergebnis aller Pruefungen steht danach in data/entdeckt.json."""
import csv
import json
import os
from datetime import datetime, timezone

import sammler

VERZEICHNIS = "kandidaten/ats-verzeichnis.csv"


def lade_kandidaten():
    bekannt = {(f["quelle"], f["kuerzel"].lower()) for f in sammler.lade_firmen()} | sammler.lade_ausschluss()
    kandidaten = []
    with open(VERZEICHNIS, encoding="utf-8", newline="") as datei:
        for zeile in csv.DictReader(datei):
            quelle = (zeile.get("ats_vendor") or "").strip().lower()
            kuerzel = (zeile.get("board_slug") or "").strip()
            name = " ".join((zeile.get("company_name") or "").replace("|", " ").split())
            if quelle in sammler.ADRESSEN and kuerzel and (quelle, kuerzel.lower()) not in bekannt:
                bekannt.add((quelle, kuerzel.lower()))
                kandidaten.append({"quelle": quelle, "kuerzel": kuerzel, "name": name})
    return kandidaten


def main():
    heute = datetime.now(timezone.utc)
    kandidaten = lade_kandidaten()
    grenze = int(os.environ.get("ENTDECKER_GRENZE", "0"))
    if grenze:
        kandidaten = kandidaten[:grenze]
    print(f"{len(kandidaten)} Kandidaten werden geprueft.")
    ergebnisse = sammler.pruefe_alle(kandidaten, heute, gleichzeitig=10)

    treffer, bericht = [], []
    for firma, (eintrag, eigene) in zip(kandidaten, ergebnisse):
        eintrag["name"] = eintrag.get("name") or firma["name"]
        bericht.append(eintrag)
        if eigene:
            treffer.append((len(eigene), firma))
    treffer.sort(key=lambda t: -t[0])

    os.makedirs("data", exist_ok=True)
    with open("data/entdeckt.json", "w", encoding="utf-8") as datei:
        json.dump({"stand": f"{heute:%Y-%m-%d %H:%M}", "geprueft": len(bericht), "treffer": len(treffer),
                   "firmen": [b for b in bericht if b.get("dach") or "fehler" not in b]},
                  datei, ensure_ascii=False, indent=1)
    if treffer:
        with open("firmen.txt", "a", encoding="utf-8") as datei:
            datei.write(f"\n# Vom Entdecker am {heute:%d.%m.%Y} gefunden: {len(treffer)} Firmen\n")
            for _, firma in treffer:
                datei.write(f"{firma['quelle']}:{firma['kuerzel']} | {firma['name'] or firma['kuerzel']}\n")
    erreichbar = sum(1 for b in bericht if "fehler" not in b)
    print(f"{erreichbar} erreichbar, {len(treffer)} mit Stellen im deutschsprachigen Raum neu aufgenommen.")


if __name__ == "__main__":
    main()
