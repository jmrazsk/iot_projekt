"""
=============================================================================
IoT Systém s Cloudovým Backendom - Flask Backend
=============================================================================
Tento súbor je SRDCE celého projektu. Je to server (backend), ktorý:
  1. Prijíma dáta z HTML formulárov (Frontend A)
  2. Spracováva výpočty (kalkulačka)
  3. Ukladá výsledky do SQLite databázy
  4. Poskytuje API endpointy pre Frontend B (IoT klient)

Autor: [Juraj Mraz]
Predmet: Internet vecí
=============================================================================
"""

# ─────────────────────────────────────────────────────────────────────────────
# IMPORT KNIŽNÍC
# ─────────────────────────────────────────────────────────────────────────────
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlite3
import datetime
import os

# ─────────────────────────────────────────────────────────────────────────────
# VYTVORENIE APLIKÁCIE
# ─────────────────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

# ─────────────────────────────────────────────────────────────────────────────
# DATABÁZA - SQLite
# ─────────────────────────────────────────────────────────────────────────────
# Absolútna cesta — funguje správne aj na Azure, nielen lokálne.
DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "databaza.db")


def inicializuj_databazu():
    """
    Vytvorí tabuľku 'vypocty', ak ešte neexistuje.
    IF NOT EXISTS = ak tabuľka už existuje, nič sa nestane (bezpečné).
    """
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vypocty (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cislo1 REAL NOT NULL,
            cislo2 REAL NOT NULL,
            operacia TEXT NOT NULL,
            vysledok REAL NOT NULL,
            cas TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    print("✅ Databáza inicializovaná.")


def uloz_do_databazy(cislo1, cislo2, operacia, vysledok):
    """
    Uloží jeden záznam o výpočte do databázy.
    """
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cas = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO vypocty (cislo1, cislo2, operacia, vysledok, cas) VALUES (?, ?, ?, ?, ?)",
        (cislo1, cislo2, operacia, vysledok, cas)
    )
    conn.commit()
    nove_id = cursor.lastrowid
    conn.close()
    return nove_id


def nacitaj_vsetky_vypocty():
    """
    Načíta VŠETKY záznamy z tabuľky 'vypocty'.
    """
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vypocty ORDER BY id DESC")
    riadky = cursor.fetchall()
    conn.close()
    return [dict(riadok) for riadok in riadky]


# ─────────────────────────────────────────────────────────────────────────────
# INICIALIZÁCIA DATABÁZY PRI ŠTARTE
# ─────────────────────────────────────────────────────────────────────────────
# OPRAVA: Toto sa musí volať TU — nie len v __main__ bloku!
# Na Azure gunicorn nespúšťa __main__, preto databáza sa nikdy nevytvorila.
inicializuj_databazu()


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 1: Hlavná stránka (Frontend A - Administračný)
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/")
def hlavna_stranka():
    return render_template("frontend_a.html")


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 2: Výpočet
# URL: /vypocet?cislo1=10&cislo2=5&operacia=plus
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/vypocet")
def vypocet():
    cislo1_str = request.args.get("cislo1", "0")
    cislo2_str = request.args.get("cislo2", "0")
    operacia = request.args.get("operacia", "plus")

    try:
        cislo1 = float(cislo1_str)
        cislo2 = float(cislo2_str)
    except ValueError:
        return jsonify({"chyba": "Neplatné čísla! Zadajte číselné hodnoty."}), 400

    if operacia == "plus":
        vysledok = cislo1 + cislo2
    elif operacia == "minus":
        vysledok = cislo1 - cislo2
    elif operacia == "krat":
        vysledok = cislo1 * cislo2
    elif operacia == "deleno":
        if cislo2 == 0:
            return jsonify({"chyba": "Delenie nulou nie je možné!"}), 400
        vysledok = cislo1 / cislo2
    else:
        return jsonify({"chyba": f"Neznáma operácia: {operacia}"}), 400

    nove_id = uloz_do_databazy(cislo1, cislo2, operacia, vysledok)

    return jsonify({
        "id": nove_id,
        "cislo1": cislo1,
        "cislo2": cislo2,
        "operacia": operacia,
        "vysledok": round(vysledok, 4),
        "cas": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 3: API - História výpočtov
# URL: /api/historia
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/historia")
def historia():
    vypocty = nacitaj_vsetky_vypocty()
    return jsonify(vypocty)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 4: API - Posledný výpočet
# URL: /api/posledny
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/posledny")
def posledny_vypocet():
    vypocty = nacitaj_vsetky_vypocty()
    if vypocty:
        return jsonify(vypocty[0])
    else:
        return jsonify({"info": "Zatiaľ neboli vykonané žiadne výpočty."}), 404


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 5: API - Štatistiky
# URL: /api/statistiky
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/statistiky")
def statistiky():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM vypocty")
    pocet = cursor.fetchone()[0]

    cursor.execute("SELECT AVG(vysledok) FROM vypocty")
    priemer = cursor.fetchone()[0]

    cursor.execute("SELECT operacia, COUNT(*) as pocet FROM vypocty GROUP BY operacia")
    podla_operacie = {row[0]: row[1] for row in cursor.fetchall()}

    conn.close()

    return jsonify({
        "celkovy_pocet": pocet,
        "priemerny_vysledok": round(priemer, 4) if priemer else 0,
        "podla_operacie": podla_operacie
    })


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 6: Frontend B (Klientsky/IoT pohľad)
# URL: /klient
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/klient")
def klientsky_pohlad():
    return render_template("frontend_b.html")


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 7: IoT Simulácia (ESP32 / senzor)
# URL: /iot/odosli?teplota=22.5&vlhkost=60
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/iot/odosli")
def iot_odosli():
    teplota = request.args.get("teplota", type=float)
    vlhkost = request.args.get("vlhkost", type=float)

    if teplota is None or vlhkost is None:
        return jsonify({"chyba": "Chýbajú parametre teplota a vlhkost!"}), 400

    return jsonify({
        "status": "ok",
        "prijate_data": {
            "teplota": teplota,
            "vlhkost": vlhkost,
            "cas": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        "sprava": "Dáta zo senzora boli úspešne prijaté."
    })


# ─────────────────────────────────────────────────────────────────────────────
# ŠTART SERVERA (len lokálne — Azure používa gunicorn)
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 IoT Backend Server beží!")
    print("=" * 60)
    print("   Frontend A (Admin):  http://localhost:5000/")
    print("   Frontend B (Klient): http://localhost:5000/klient")
    print("   API História:        http://localhost:5000/api/historia")
    print("   API Štatistiky:      http://localhost:5000/api/statistiky")
    print("   IoT Endpoint:        http://localhost:5000/iot/odosli?teplota=22&vlhkost=60")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=True)