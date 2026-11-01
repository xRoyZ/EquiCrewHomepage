# EquiCrew – Website mit Kontaktformular

Die neue Firmenwebsite der EquiCrew FlexCo („smarte energie – fair verteilte KI“). Sie löst die bisherige Seite unter www.equicrew.com ab und zeigt dieselben Inhalte in frischem Design auf Deutsch: Startseite, Über uns, EquiCube, Kontakt, Impressum und Datenschutz. Die Website besteht aus statischen HTML-Seiten ohne Build-Schritt. Das Kontaktformular ist ein echtes Formular: Ein kleines FastAPI-Backend prüft die Eingaben, schützt sich gegen Spam (Honeypot, Ratenlimit, Größenlimit) und schickt jede Nachricht per SMTP direkt an office@equicrew.com.

## Tech-Stack

- **Frontend** (`frontend/`): Vanilla HTML, CSS und JavaScript (ES-Module), mehrere statische Seiten, kein Build-Tool; Schriften und Bilder werden vom eigenen Ursprung ausgeliefert
- **Backend** (`backend/`): Python 3.12+, FastAPI, Uvicorn, pydantic (Validierung), `smtplib`/`email` aus der Standardbibliothek für den Versand
- **Tests**: `node --test` für die Frontend-Logik, `pytest` für das Backend

## Projektstruktur

```
dev.py                 Entwicklungsstart: Backend und Website gemeinsam
RUN.json               maschinenlesbare Startbeschreibung
backend/
  requirements.txt     Python-Abhängigkeiten
  app/main.py          create_app(), CORS, Middleware, Router
  app/config.py        Settings aus den Umgebungsvariablen
  app/errors.py        einheitliche Fehlerantworten {"detail": "..."}
  app/health.py        GET /api/health
  app/contact.py       POST /api/contact
  app/ratelimit.py     Ratenlimit pro Client-IP
  app/body_limit.py    Obergrenze für die Größe des Request-Bodys
  tests/               pytest-Tests
frontend/
  index.html           Start                 /
  ueber-uns/           Über uns              /ueber-uns/
  equicube/            EquiCube              /equicube/
  kontakt/             Kontakt               /kontakt/
  impressum/           Impressum             /impressum/
  datenschutz/         Datenschutz           /datenschutz/
  css/ js/ fonts/ assets/img/
  dev_server.py        statischer Entwicklungsserver
  tests/               node:test-Tests
```

## Installation

Voraussetzungen: Python 3.12 oder neuer, Node.js 20 oder neuer (nur für die Frontend-Tests).

```bash
git clone <repository-url>
cd <repository>
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python3 -m pip install -r backend/requirements.txt
```

Das Frontend hat keine Abhängigkeiten, die installiert werden müssen.

## Starten (Entwicklung)

Ein Befehl im Wurzelverzeichnis startet Backend und Website gemeinsam:

```bash
python3 dev.py                     # Windows: py dev.py
```

- Website: http://127.0.0.1:8080/
- Backend: http://127.0.0.1:8000/api/health

`dev.py` setzt dabei `API_BASE_URL` für die Website und `FRONTEND_ORIGIN` für das Backend passend zueinander. Andere Ports: `python3 dev.py --api-port 9000 --web-port 9080`. **Strg+C** beendet beide Prozesse.

Die Seiten müssen über einen HTTP-Server geöffnet werden – nicht per Doppelklick als `file://`, denn dann blockiert der Browser ES-Module und Anfragen an das Backend.

Ohne SMTP-Zugangsdaten startet das Backend trotzdem: `GET /api/health` antwortet mit 200, das Kontaktformular meldet dann einen Versandfehler (503) mit Hinweis auf office@equicrew.com. Für echten Versand die SMTP-Variablen (siehe unten) vor dem Start setzen, z. B.:

```bash
export SMTP_HOST=smtp.example.com
export SMTP_PORT=587
export SMTP_USER=website@example.com
export SMTP_PASSWORD='<passwort>'
export SMTP_FROM=website@example.com
python3 dev.py
```

Nur das Backend starten:

```bash
cd backend
python3 -m uvicorn app.main:app --port 8000
```

## Betrieb (Produktion)

Es gibt keinen Build-Schritt. Der Ordner `frontend/` wird so, wie er ist, von einem beliebigen statischen Webserver ausgeliefert; jede Seite ist ein eigenes HTML-Dokument (`/impressum/` → `impressum/index.html`). Das Backend läuft mit

```bash
cd backend
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

hinter demselben Webserver, der `/api/` an Uvicorn weiterleitet. Liegen Website und Backend auf demselben Ursprung, bleibt `API_BASE` in `frontend/js/config.js` leer (`""`) und es ist kein CORS nötig; liegt das Backend auf einem anderen Ursprung, `FRONTEND_ORIGIN` auf die Adresse der Website setzen und `API_BASE` auf die Adresse des Backends.

## Umgebungsvariablen

| Variable | Dienst | Bedeutung | Standard |
|---|---|---|---|
| `SMTP_HOST` | Backend | Hostname des SMTP-Servers | – (ohne: Versand antwortet 503) |
| `SMTP_PORT` | Backend | Port des SMTP-Servers | `587` |
| `SMTP_USER` | Backend | Benutzername für die SMTP-Anmeldung | – |
| `SMTP_PASSWORD` | Backend | Passwort für die SMTP-Anmeldung (geheim, nie ins Repository) | – |
| `SMTP_FROM` | Backend | Absenderadresse der Kontakt-Mails | – (ohne: Versand antwortet 503) |
| `CONTACT_RECIPIENT` | Backend | Empfänger der Kontakt-Mails | `office@equicrew.com` |
| `FRONTEND_ORIGIN` | Backend | einziger Ursprung, dem CORS erlaubt wird | – (ohne: kein CORS) |
| `API_BASE_URL` | Website | Adresse des Backends, die `dev_server.py` unter `/js/config.js` ausliefert | `""` (gleicher Ursprung) |

Der Versand ist aktiv, sobald `SMTP_HOST`, `SMTP_PORT` und `SMTP_FROM` gesetzt sind.

## Bedienung

### Die Seiten

- **Start** (`/`): Claim „smarte energie – fair verteilte KI“, Leitbild, EquiCube-Teaser mit Link zur EquiCube-Seite, Team-Teaser mit Link zu Über uns und der Call-to-Action „Neugierig geworden?“ mit Link zu Kontakt.
- **Über uns** (`/ueber-uns/`): „Über die Crew“, Teamfoto und die drei Gründerkarten (Michael Hochstöger, Christian Hinterdorfer, Christian Hinterreiter) mit Porträt und E-Mail-Link.
- **EquiCube** (`/equicube/`): Produktbeschreibung mit Cube-Rendering, Button „Jetzt anfragen!“ (führt zu Kontakt), die vier Merkmale und „Vorteile des EquiCubes“.
- **Kontakt** (`/kontakt/`): Adresse, E-Mail- und Telefon-Link und das Kontaktformular (Vorname, Nachname, E-Mail, Nachricht, „Senden“) mit Datenschutzhinweis.
- **Impressum** (`/impressum/`): Angaben nach § 5 ECG, § 14 UGB und Offenlegung nach § 25 MedienG.
- **Datenschutz** (`/datenschutz/`): Datenschutzerklärung nach Art. 13 DSGVO.

Die Kopfnavigation (Start, Über uns, EquiCube, Kontakt, Impressum) markiert die aktuelle Seite; auf Handybreite klappt sie in einen Menü-Button ein. Der Footer verlinkt Kontakt, Impressum und Datenschutz.

### Das Kontaktformular

Fehler erscheinen erst, nachdem ein Feld bearbeitet und verlassen oder das Absenden versucht wurde. Während des Sendens ist der Button deaktiviert. Nach erfolgreichem Versand ersetzt „Danke für deine Nachricht!“ das Formular; schlägt der Versand fehl, erscheint eine Fehlermeldung mit office@equicrew.com und der eingegebene Text bleibt erhalten.

### Backend-API

Alle Fehler außer 422 haben die Form `{"detail": "<kurzer deutscher Text>"}` – nie mit Stacktrace, Exception-Text oder SMTP-Zugangsdaten.

#### `GET /api/health`

Lebenszeichen, antwortet auch ohne SMTP-Konfiguration.

```json
200 {"status": "ok"}
```

#### `POST /api/contact`

Body (JSON):

```json
{
  "first_name": "Maria",
  "last_name": "Muster",
  "email": "maria@example.com",
  "message": "Ich interessiere mich für den EquiCube.",
  "website": ""
}
```

| Feld | Regel |
|---|---|
| `first_name`, `last_name` | 1–100 Zeichen, keine Zeilenumbrüche |
| `email` | gültige Adresse, höchstens 254 Zeichen, keine Zeilenumbrüche |
| `message` | 1–5000 Zeichen |
| `website` | Honeypot, muss leer bleiben (Standard `""`) |

Antworten:

| Status | Body | Bedeutung |
|---|---|---|
| 200 | `{"status": "sent"}` | Nachricht verschickt (bei ausgefülltem Honeypot ebenfalls 200, aber ohne Versand) |
| 413 | `{"detail": "..."}` | Body größer als 32 768 Bytes |
| 422 | FastAPI-Validierungsfehler | ungültige Eingabe |
| 429 | `{"detail": "..."}` | mehr als 5 Einsendungen in 600 Sekunden von derselben IP |
| 503 | `{"detail": "..."}` | SMTP nicht konfiguriert oder Versand fehlgeschlagen |
| 500 | `{"detail": "..."}` | unerwarteter Fehler |

Beispiel:

```bash
curl -X POST http://127.0.0.1:8000/api/contact \
  -H 'Content-Type: application/json' \
  -d '{"first_name":"Maria","last_name":"Muster","email":"maria@example.com","message":"Hallo!"}'
```

Die Mail geht an `CONTACT_RECIPIENT` und enthält Name, Nachricht und die Absenderadresse als Reply-To. Für das Ratenlimit zählt ausschließlich die IP der Verbindung (`X-Forwarded-For` wird nie gelesen); sie wird nur im Arbeitsspeicher und höchstens für die Dauer des Zeitfensters gehalten.

## Tests

Backend (aus `backend/`):

```bash
cd backend
python3 -m pytest
```

Frontend (aus `frontend/`):

```bash
cd frontend
node --test tests/*.test.mjs
```

## Funktionen

- Sechs eigenständige, statisch auslieferbare Seiten mit eigenem Titel und Meta-Beschreibung
- Responsive Layout (360 px bis 1440 px) mit einklappbarer Navigation
- Keine Anfragen an fremde Hosts: Schriften, Skripte, Stylesheets und Bilder kommen vom eigenen Ursprung
- Kontaktformular mit Prüfung im Browser und im Backend, Lade-, Erfolgs- und Fehlerzustand
- Versand per SMTP an office@equicrew.com mit Reply-To auf die Absenderadresse
- Spamschutz: Honeypot-Feld, Ratenlimit pro IP, Obergrenze für die Body-Größe
- Schutz vor Header-Injection (keine Zeilenumbrüche in Name und E-Mail)
- Einheitliche deutsche Fehlerantworten ohne interne Details
- Backend startet ohne SMTP-Konfiguration und meldet sich unter `/api/health`
- Impressum und Datenschutzerklärung nach österreichischem Recht und DSGVO
