#!/bin/bash
# =============================================================================
# Automatický testovací skript pre variantu A (Flask backend) [VERZIA 3]
# =============================================================================
# POUŽITIE:
#   1) Skopírujte študentove app.py + frontend.html do nového adresára
#   2) Skopírujte test.sh + requirements.txt do toho adresára
#   3) Spustite:   bash test.sh
#
# Skript otestuje 4 backend chyby + endpoint /api/podrobne.
# Bug #5 (frontend.html — HTTP metóda) sa testuje vizuálne.
# =============================================================================

set -u

rm -f hlasy.json

if [ ! -f "app.py" ]; then
    echo "❌ Nenašiel som app.py v aktuálnom adresári."
    exit 1
fi

echo "Spúšťam Flask server..."
python3 app.py > server.log 2>&1 &
SERVER_PID=$!

cleanup() {
    kill $SERVER_PID 2>/dev/null || true
    wait $SERVER_PID 2>/dev/null || true
    rm -f hlasy.json server.log
}
trap cleanup EXIT

sleep 2

if ! kill -0 $SERVER_PID 2>/dev/null; then
    echo "❌ Server sa nespustil. Pozri server.log:"
    cat server.log
    exit 1
fi

BASE="http://localhost:8000"
OK=0
FAIL=0
BODY=0

check() {
    local label="$1"
    local expected="$2"
    local actual="$3"
    local body="$4"
    if [ "$expected" = "$actual" ]; then
        echo "  ✅ $label  (+${body} b)"
        OK=$((OK + 1))
        BODY=$(awk "BEGIN {print $BODY + $body}")
    else
        echo "  ❌ $label  (očakávané: '$expected', dostal: '$actual')"
        FAIL=$((FAIL + 1))
    fi
}

echo ""
echo "=========================================="
echo "  TESTY OPRÁV CHÝB (po 1.0 b za opravu)"
echo "=========================================="

# CHYBA #4: Missing global → first POST should not crash
rm -f hlasy.json
STATUS=$(curl -s -X POST -o /dev/null -w "%{http_code}" "$BASE/api/hlasuj?moznost=A")
check "CHYBA #4: prvé volanie /api/hlasuj → 200 (nie 500)" "200" "$STATUS" "1.0"

# CHYBA #1: Validation must reject invalid moznost
rm -f hlasy.json
STATUS=$(curl -s -X POST -o /dev/null -w "%{http_code}" "$BASE/api/hlasuj?moznost=XYZ")
check "CHYBA #1: moznost='XYZ' → 400 (validácia odmietne)" "400" "$STATUS" "1.0"

# CHYBA #2: Defensive dict access — simulate prior invalid data
rm -f hlasy.json
# Write a record with invalid moznost directly to simulate edge case
cat > hlasy.json <<'JSONEOF'
[
  {"moznost": "A", "cas": "2024-01-15 10:00:00"},
  {"moznost": "Z", "cas": "2024-01-15 10:01:00"},
  {"moznost": "B", "cas": "2024-01-15 10:02:00"}
]
JSONEOF
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/vysledky")
check "CHYBA #2: /api/vysledky pri neznámej moznost v dátach → 200 (nie 500)" "200" "$STATUS" "1.0"

# CHYBA #3: Slice direction — last N, not first N
rm -f hlasy.json
curl -s -X POST "$BASE/api/hlasuj?moznost=A" > /dev/null
sleep 0.05
curl -s -X POST "$BASE/api/hlasuj?moznost=B" > /dev/null
sleep 0.05
curl -s -X POST "$BASE/api/hlasuj?moznost=C" > /dev/null
LAST=$(curl -s "$BASE/api/posledne?n=1" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['moznost'] if d else '?')" 2>/dev/null || echo "?")
check "CHYBA #3: /api/posledne?n=1 vráti posledný (C), nie prvý (A)" "C" "$LAST" "1.0"

echo ""
echo "=========================================="
echo "  ENDPOINT /api/podrobne (max 1.5 b)"
echo "=========================================="

rm -f hlasy.json
for i in 1 2 3; do curl -s -X POST "$BASE/api/hlasuj?moznost=A" > /dev/null; done
for i in 1 2; do curl -s -X POST "$BASE/api/hlasuj?moznost=B" > /dev/null; done

STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/podrobne")
check "Endpoint existuje (HTTP 200)" "200" "$STATUS" "0.25"

STAT=$(curl -s "$BASE/api/podrobne")

CELKOM=$(echo "$STAT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('celkom','?'))" 2>/dev/null || echo "?")
check "celkom = 5" "5" "$CELKOM" "0.25"

POCET_A=$(echo "$STAT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('pocty',{}).get('A','?'))" 2>/dev/null || echo "?")
check "pocty.A = 3" "3" "$POCET_A" "0.25"

PCT_A=$(echo "$STAT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('percenta',{}).get('A','?'))" 2>/dev/null || echo "?")
check "percenta.A = 60.0" "60.0" "$PCT_A" "0.5"

POCET_C=$(echo "$STAT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('pocty',{}).get('C','?'))" 2>/dev/null || echo "?")
check "pocty.C = 0 (žiadne hlasy)" "0" "$POCET_C" "0.125"

LAST_CAS=$(echo "$STAT" | python3 -c "import sys,json; d=json.load(sys.stdin); print('non-null' if d.get('posledny_hlas') else 'null')" 2>/dev/null || echo "?")
check "posledny_hlas != null" "non-null" "$LAST_CAS" "0.125"

echo ""
echo "=========================================="
echo "  AUTOMATICKÝ VÝSLEDOK"
echo "=========================================="
echo "  Úspešné: $OK   Neúspešné: $FAIL"
echo "  Body z automatu: $BODY / 5.5 b"
echo ""
echo "=========================================="
echo "  MANUÁLNA KONTROLA (zostávajúce body)"
echo "=========================================="
echo "  • Komentáre k 5 opravám:                       5 × 0.5 b = 2.5 b"
echo "  • CHYBA #5 vo frontend.html (HTTP metóda):     1.0 b"
echo "  • Funkčné nasadenie na Azure (otvoriť URL):    1.0 b"
echo ""
echo "  CELKOVO MOŽNÝCH: 10.0 b"
echo "=========================================="
