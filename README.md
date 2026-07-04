# HEAD-UP DISPLAY CU FUNCȚIONALITĂȚI DE TELEMETRIE ȘI GESTIONARE A ERORILOR
## 1. Repository

Codul sursă al proiectului este disponibil la adresa:

```text
https://github.com/serban-mihaltan/HEAD-UP-DISPLAY-CU-FUNC-IONALIT-I-DE-TELEMETRIE-I-GESTIONARE-A-ERORILOR
```

Repository-ul conține codul sursă complet al aplicației, fără fișiere binare compilate, fără directoare de build și fără executabile generate. Fișierele executabile sau instalatoarele, dacă sunt generate, trebuie publicate separat în secțiunea **Releases** a repository-ului.

## 2. Descrierea proiectului

Acest proiect prezintă o aplicație **Head-Up Display personalizabilă**, destinată afișării în timp real a informațiilor relevante despre vehicul prin intermediul unui adaptor **ELM327 compatibil OBD-II**.

Scopul aplicației este de a oferi șoferului acces rapid la date precum viteza, turația motorului, poziția accelerației, temperatura lichidului de răcire, nivelul combustibilului, tensiunea bateriei și informații de diagnosticare. Datele sunt afișate într-o interfață clară, configurabilă și ușor de urmărit.

Aplicația este organizată modular, separând funcțiile principale în componente distincte: interfață grafică, comunicare OBD, colectarea datelor, diagnosticare, exportul telemetriei și gestionarea setărilor. Această structură facilitează întreținerea, testarea și extinderea ulterioară a sistemului.

Interfața principală oferă un tablou de bord configurabil, alcătuit din widget-uri mobile și redimensionabile. Acestea pot afișa informațiile în format digital sau analogic. Utilizatorul poate adapta modul de afișare în funcție de preferințe, iar funcția de oglindire permite reflectarea informațiilor pe parbriz, menținând lizibilitatea acestora în modul HUD.

Pe lângă afișarea telemetriei în timp real, aplicația include monitorizarea evoluției parametrilor în timp și funcții de diagnosticare prin citirea și interpretarea codurilor de eroare DTC. Astfel, proiectul oferă o soluție practică pentru monitorizarea parametrilor importanți ai mașinii și accesarea rapidă a informațiilor de diagnosticare.

Aplicația a fost testată în fază inițială utilizând un emulator de ELM327, dezvoltat in C#/.NET cu interfață WPF.Acesta simulează comunicarea OBD-II prin TCP/IP sau port serial COM, permițând testarea fără conectarea directă la un autovehicul real.
Codul sursă este disponibil la adresa:

```text
https://github.com/serban-mihaltan/ELM327_Emulator
```

## 3. Funcționalități principale

- afișarea în timp real a datelor preluate prin OBD-II;
- conectare la vehicul prin adaptor ELM327;
- afișarea valorilor în widget-uri digitale și analogice;
- personalizarea poziției, dimensiunii și culorilor widget-urilor;
- utilizarea presetărilor pentru interfața HUD;
- funcție de oglindire pentru folosirea aplicației ca Head-Up Display;
- monitorizarea evoluției parametrilor de telemetrie;
- citirea codurilor de eroare DTC;
- interpretarea codurilor DTC folosind un catalog local;
- ștergerea codurilor DTC, dacă vehiculul și adaptorul permit acest lucru;
- exportul datelor de telemetrie în format CSV sau XLSX.

## 4. Structura proiectului

```text
.
├── presets/
│   └── *.json
├── src/
│   └── hud/
│       ├── app.py
│       ├── data/
│       │   └── dtc_catalog.csv
│       ├── models/
│       │   ├── dtc.py
│       │   ├── enums.py
│       │   ├── settings.py
│       │   └── telemetry.py
│       ├── services/
│       │   ├── dtc_service.py
│       │   ├── obd_service.py
│       │   ├── settings_service.py
│       │   └── telemetry_export.py
│       ├── ui/
│       │   ├── main_window.py
│       │   ├── screens/
│       │   │   ├── dtc_screen.py
│       │   │   ├── main_screen.py
│       │   │   ├── settings_screen.py
│       │   │   └── telemetry_screen.py
│       │   └── widgets/
│       │       ├── dashboard_canvas.py
│       │       ├── dashboard_widget.py
│       │       ├── telemetry_cards.py
│       │       └── top_bar.py
│       └── utils/
│           ├── color.py
│           └── gauge_math.py
├── requirements.txt
├── README.md
└── start.py
```

## 5. Livrabilele proiectului

Repository-ul include următoarele livrabile:

- codul sursă complet al aplicației;
- fișierele de configurare și presetările HUD;
- catalogul local pentru interpretarea codurilor DTC;
- fișierul `requirements.txt` cu bibliotecile necesare;
- fișierul `README.md` cu descrierea proiectului, pașii de instalare, rulare și generare a executabilului.


## 6. Cerințe software

Pentru rularea aplicației sunt necesare:

- Python 3.13.5;
- Git;
- pip;
- sistem de operare Windows sau Linux;
- adaptor ELM327 compatibil OBD-II;
- port OBD-II disponibil pe vehicul.

Bibliotecile Python necesare sunt definite în fișierul `requirements.txt`:

```text
PySide6>=6.6,<7
obd>=0.7.2
pyserial>=3.5
```

## 7. Instalarea aplicației

### 7.1. Clonarea repository-ului

```bash
git clone https://github.com/serban-mihaltan/HEAD-UP-DISPLAY-CU-FUNC-IONALIT-I-DE-TELEMETRIE-I-GESTIONARE-A-ERORILOR
cd HEAD-UP-DISPLAY-CU-FUNC-IONALIT-I-DE-TELEMETRIE-I-GESTIONARE-A-ERORILOR
```

### 7.2. Instalare pe Windows



```bat
py -3.13 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 7.3. Instalare pe Linux

```bash
python3.15 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Pe Linux, pentru acces la adaptorul conectat pe port serial, poate fi necesară adăugarea utilizatorului în grupul `dialout`:

```bash
sudo usermod -a -G dialout $USER
```

După rularea comenzii, este necesară delogarea și autentificarea din nou.

## 8. Lansarea aplicației

Aplicația se lansează din rădăcina proiectului cu:

```bash
python start.py
```

După pornire, conexiunea la adaptorul ELM327 se configurează din interfața aplicației, în ecranul de setări.

Exemple de porturi pentru Windows:

```text
COM3
COM4
COM5
```

Exemple de porturi pentru Linux:

```text
/dev/ttyUSB0
/dev/ttyACM0
```

Aplicația poate fi pornită și fără adaptor conectat, însă valorile de telemetrie nu vor fi actualizate până la stabilirea conexiunii cu adaptorul OBD-II.

## 9. Pași de compilare / generare executabil

Aplicația este dezvoltată în Python, deci nu necesită o etapă de compilare clasică. Pentru distribuire, se poate genera un executabil folosind **PyInstaller**.

PyInstaller se instalează separat, deoarece este necesar doar pentru generarea executabilului, nu pentru rularea aplicației:

```bash
pip install pyinstaller
```

### 9.1. Generare executabil pentru Windows

Comanda se rulează pe Windows, din rădăcina proiectului:

pentru **Command Prompt/CMD**
```bat
pyinstaller --noconfirm --windowed --name AutomotiveHUD ^
  --paths src ^
  --add-data "src/hud/data;hud/data" ^
  --add-data "presets;presets" ^
  start.py
```
sau

pentru **PowerShell**
```bat
pyinstaller --noconfirm --windowed --name AutomotiveHUD --paths src --add-data "src/hud/data;hud/data" --add-data "presets;presets" start.py
```
Executabilul generat se va afla în:

```text
dist/AutomotiveHUD/
```

Fișierul principal de lansare va fi:

```text
dist/AutomotiveHUD/AutomotiveHUD.exe
```

### 9.2. Generare executabil pentru Linux

Comanda se rulează pe Linux, din rădăcina proiectului:

```bash
pyinstaller --noconfirm --windowed --name automotive-hud \
  --paths src \
  --add-data "src/hud/data:hud/data" \
  --add-data "presets:presets" \
  start.py
```

Executabilul generat se va afla în:

```text
dist/automotive-hud/
```

Fișierul principal de lansare va fi:

```text
dist/automotive-hud/automotive-hud
```

## 10. Observații privind utilizarea

- Disponibilitatea parametrilor OBD depinde de vehicul, adaptor și protocolul suportat.
- Unele vehicule nu expun toți parametrii disponibili în aplicație.
- Citirea și ștergerea codurilor DTC pot depinde de compatibilitatea adaptorului și de modulele electronice ale vehiculului.
- Pentru folosirea în mașină, aplicația trebuie utilizată într-un mod care nu afectează atenția șoferului și nu obstrucționează câmpul vizual.

