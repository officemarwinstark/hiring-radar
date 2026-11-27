"""Hiring-Radar, Sammler: liest offene Stellen aus oeffentlichen Greenhouse-Listen
und baut daraus eine Datei (data/stellen.json) und eine Seite (docs/index.html)."""
import html
import json
import os
import urllib.request
from datetime import datetime, timezone

QUELLE = "https://boards-api.greenhouse.io/v1/boards/{}/jobs"


def lade_firmen():
    with open("firmen.txt", encoding="utf-8") as datei:
        zeilen = [zeile.strip() for zeile in datei]
    return [z for z in zeilen if z and not z.startswith("#")]


def hole_stellen(kuerzel):
    anfrage = urllib.request.Request(
        QUELLE.format(kuerzel), headers={"User-Agent": "hiring-radar"}
    )
    with urllib.request.urlopen(anfrage, timeout=30) as antwort:
        return json.load(antwort).get("jobs", [])


def tage_seit(datum_text, heute):
    try:
        return max((heute - datetime.fromisoformat(datum_text)).days, 0)
    except (TypeError, ValueError):
        return None


def sammle(heute):
    stellen, fehler = [], []
    for kuerzel in lade_firmen():
        try:
            jobs = hole_stellen(kuerzel)
        except Exception as grund:  # eine kaputte Firma stoppt nicht den Rest
            fehler.append(f"{kuerzel}: {grund}")
            continue
        for job in jobs:
            erstmals = job.get("first_published") or job.get("updated_at")
            stellen.append({
                "firma": job.get("company_name") or kuerzel,
                "titel": (job.get("title") or "").strip(),
                "ort": (job.get("location") or {}).get("name") or "",
                "online_seit": (erstmals or "")[:10],
                "tage_offen": tage_seit(erstmals, heute),
                "link": job.get("absolute_url") or "",
            })
    stellen.sort(key=lambda s: -(s["tage_offen"] or 0))
    return stellen, fehler


def baue_seite(stellen, heute):
    zeilen = []
    for s in stellen:
        tage = "" if s["tage_offen"] is None else s["tage_offen"]
        link = html.escape(s["link"], quote=True)
        titel = html.escape(s["titel"])
        if link.startswith("https://"):
            titel = f'<a href="{link}" rel="noopener">{titel}</a>'
        zeilen.append(
            f"<tr><td>{html.escape(s['firma'])}</td><td>{titel}</td>"
            f"<td>{html.escape(s['ort'])}</td><td>{tage}</td></tr>"
        )
    firmen = len({s["firma"] for s in stellen})
    return f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hiring-Radar</title>
<style>
body{{font-family:system-ui,sans-serif;margin:0 auto;max-width:1000px;padding:24px 16px;color:#1c2430}}
h1{{margin:0 0 4px}} p{{margin:0 0 16px;color:#566}}
input{{width:100%;padding:10px;font-size:16px;box-sizing:border-box;margin-bottom:12px}}
.rahmen{{overflow-x:auto}} table{{border-collapse:collapse;width:100%}}
th,td{{text-align:left;padding:8px;border-bottom:1px solid #dde}} th{{background:#f1f4f8}}
td:last-child,th:last-child{{text-align:right}}
</style></head><body>
<h1>Hiring-Radar</h1>
<p>{len(stellen)} offene Stellen bei {firmen} Firmen. Stand: {heute:%d.%m.%Y}.</p>
<input id="suche" placeholder="Filtern, zum Beispiel: sales berlin">
<div class="rahmen"><table><thead><tr><th>Firma</th><th>Stelle</th><th>Ort</th><th>Tage offen</th></tr></thead>
<tbody id="liste">
{chr(10).join(zeilen)}
</tbody></table></div>
<script>
const suche = document.getElementById("suche");
const reihen = [...document.querySelectorAll("#liste tr")];
suche.addEventListener("input", () => {{
  const worte = suche.value.toLowerCase().split(" ").filter(Boolean);
  for (const r of reihen) {{
    const text = r.textContent.toLowerCase();
    r.hidden = !worte.every(w => text.includes(w));
  }}
}});
</script>
</body></html>
"""


def main():
    heute = datetime.now(timezone.utc)
    stellen, fehler = sammle(heute)
    os.makedirs("data", exist_ok=True)
    os.makedirs("docs", exist_ok=True)
    with open("data/stellen.json", "w", encoding="utf-8") as datei:
        json.dump(stellen, datei, ensure_ascii=False, indent=1)
    with open("docs/index.html", "w", encoding="utf-8") as datei:
        datei.write(baue_seite(stellen, heute))
    print(f"{len(stellen)} Stellen gespeichert.")
    for zeile in fehler:
        print("Nicht erreichbar:", zeile)
    if not stellen:
        raise SystemExit("Keine einzige Stelle gefunden. Bitte firmen.txt pruefen.")


if __name__ == "__main__":
    main()
