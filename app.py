from flask import Flask, request, jsonify, send_from_directory  # OPRAVA #1: sendfromdirectory → send_from_directory
import json
import os
import datetime

app = Flask(__name__)  # OPRAVA #2: name → __name__
SUBOR = "hlasy.json"

total_hlasov = 0

def nacitaj_hlasy():
    if not os.path.exists(SUBOR):
        return []
    with open(SUBOR, "r", encoding="utf-8") as f:
        return json.load(f)

def uloz_hlas(hlas):
    hlasy = nacitaj_hlasy()
    hlasy.append(hlas)
    with open(SUBOR, "w", encoding="utf-8") as f:
        json.dump(hlasy, f, ensure_ascii=False, indent=2)

@app.route("/api/hlasuj", methods=["POST"])
def hlasuj():
    moznost = request.args.get("moznost", "").strip().upper()

    if moznost not in ("A", "B", "C"):  # OPRAVA #3: pôvodne kontrolovala iba ci je prazdny string if not moznost: co neosetruje ak by bol input hocijake ine pismeno ako ABC co by bol problem pretoze slovnik pocty ma iba tieto tri pismena 
        return jsonify({"chyba": "Neplatná moznost"}), 400

    global total_hlasov  # OPRAVA #4: chýbalo global — Python hodí error ak sa snazim robit += vo funkcii bez global
    total_hlasov += 1

    hlas = {
        "moznost": moznost,
        "cas": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    uloz_hlas(hlas)

    return jsonify(hlas)

@app.route("/api/vysledky")
def vysledky():
    hlasy = nacitaj_hlasy()

    pocty = {"A": 0, "B": 0, "C": 0}
    for h in hlasy:
        pocty[h["moznost"]] += 1


    return jsonify(pocty)

@app.route("/api/posledne")
def posledne():
    n = request.args.get("n", default=10, type=int)
    hlasy = nacitaj_hlasy()
    return jsonify(hlasy[:n])  

@app.route("/api/podrobne")
def podrobne():
    hlasy = nacitaj_hlasy()

    pocty = {"A": 0, "B": 0, "C": 0}
    for h in hlasy:
        if h["moznost"] in pocty:
            pocty[h["moznost"]] += 1

    celkom = sum(pocty.values())

    if celkom > 0:
        percenta = {m: round(pocty[m] / celkom * 100, 1) for m in pocty}
    else:
        percenta = {"A": 0.0, "B": 0.0, "C": 0.0}

    posledny_hlas = hlasy[-1]["cas"] if hlasy else None

    return jsonify({
        "pocty": pocty,
        "percenta": percenta,
        "celkom": celkom,
        "posledny_hlas": posledny_hlas
    })

@app.route("/")
def index():
    return send_from_directory(".", "frontend.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
