# SC Solutions - AC Invoice App

Professional PDF invoice generator for AC service, repair, installation and resale businesses.

## Features
- Create Proforma PDF invoices with 3 professional templates
- GST (CGST + SGST) calculation per item
- Suggested items catalog (Split, Cassette, Ductable, Resale)
- Amount in words (Indian number system)
- Invoice history
- Configurable company settings (name, address, GSTIN, PAN, phone, terms)

## Project Structure
- `main.py` — Kivy Android app (for APK build)
- `app.py` — Flask web app (runs in browser)
- `invoice_templates.py` — Shared PDF generation module
- `templates/index.html` + `static/js/app.js` + `static/css/style.css` — Web UI
- `buildozer.spec` — Android build configuration
- `.github/workflows/build-apk.yml` — GitHub Actions CI

## 3 PDF Templates
- **Professional (A)** — Corporate blue styling with gradient header
- **Modern (B)** — Clean horizontal rules with dark sidebar
- **Classic (C)** — Traditional navy grid with gold highlights

## Build Android APK

### Option 1: GitHub Actions (Recommended)
Push to `main` branch — the GitHub Actions workflow automatically builds the APK.
Download it from the **Actions** tab artifacts.

### Option 2: Docker
```bash
docker pull kivy/buildozer
docker run -it --rm -v "$PWD":/home/buildozer/buildozer kivy/buildozer
# Inside container:
buildozer -v android debug
```

### Option 3: Local Linux
```bash
sudo apt-get install -y git zip unzip openjdk-17-jdk python3-pip autoconf libtool pkg-config zlib1g-dev libncurses5-dev cmake libffi-dev libssl-dev automake
pip install buildozer cython
buildozer -v android debug
```

## Run the Web App
```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000 in your browser.

## Requirements
- Python 3.11+
- Kivy 2.3.0
- ReportLab
- Num2Words
- Pillow
- Flask

## License
MIT
