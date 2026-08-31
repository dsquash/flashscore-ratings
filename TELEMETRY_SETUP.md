# Configurare Telemetrie — Google Sheets

## Ce primesti
Un Google Sheet cu cate un rand per run, cu:
- Data/ora, platforma (Win/Mac), versiune app
- Hostname (ca sa stii de pe ce masina)
- URL Flashscore + Sofascore
- Cati jucatori gasiti / negasiti
- Jucatorii negasiti (cu nume)
- Durata rularii

---

## Pasul 1 — Creeaza Google Sheet

1. Du-te la https://sheets.google.com si creeaza un sheet nou
2. Numeste-l "Flashscore Telemetrie"
3. Pe primul rand scrie header-ele (optional, se adauga automat la primul run):
   `Timestamp | Event | Platform | Version | Hostname | Flashscore URL | Sofascore URL | OK | Not Found | Errors | Duration (s)`

---

## Pasul 2 — Creeaza Web App (Google Apps Script)

1. In sheet: **Extensii → Apps Script**
2. Sterge codul default si lipeste:

```javascript
function doPost(e) {
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    var data  = JSON.parse(e.postData.contents);

    // Adauga header daca sheet-ul e gol
    if (sheet.getLastRow() === 0) {
      sheet.appendRow([
        "Timestamp", "Event", "Platform", "Version", "Hostname",
        "Flashscore URL", "Sofascore URL", "OK", "Not Found", "Errors", "Duration (s)"
      ]);
      sheet.getRange(1, 1, 1, 11).setFontWeight("bold");
    }

    sheet.appendRow([
      data.timestamp      || "",
      data.event          || "",
      data.platform       || "",
      data.version        || "",
      data.hostname       || "",
      data.flashscore_url || "",
      data.sofascore_url  || "",
      data.players_ok     || 0,
      data.players_not_found || 0,
      data.errors         || "",
      data.duration_sec   || 0,
    ]);

    return ContentService
      .createTextOutput(JSON.stringify({ status: "ok" }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ status: "error", msg: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

// Test rapid din browser (GET)
function doGet(e) {
  return ContentService.createTextOutput("Flashscore Telemetrie OK");
}
```

3. Salveaza (Ctrl+S) — numeste proiectul "Flashscore Telemetrie"

---

## Pasul 3 — Deploiaza ca Web App

1. Click **Deploy → New deployment**
2. **Select type** → **Web App**
3. Seteaza:
   - Description: `Flashscore Telemetrie`
   - Execute as: **Me**
   - Who has access: **Anyone**
4. Click **Deploy**
5. Autorizeaza (prima data)
6. Copiaza **Web App URL** — arata ca:
   `https://script.google.com/macros/s/AKfycby.../exec`

---

## Pasul 4 — Pune URL-ul in telemetry.py

Deschide `_DO NOT TOUCH_/telemetry.py` si inlocuieste:
```python
TELEMETRY_URL = "https://script.google.com/macros/s/INLOCUIESTE_CU_URL_TAU/exec"
```
cu URL-ul copiat la pasul anterior.

Salveaza fisierul si fa un nou push pe GitHub (sau editeaza direct in GitHub).

---

## Verificare

Dupa prima rulare, in Google Sheet ar trebui sa apara un rand nou automat.
Daca nu apare, verifica:
- URL-ul din telemetry.py e corect
- Web App-ul e deployed cu "Anyone" access
- Conexiunea la internet functioneaza pe masina user-ului
