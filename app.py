import os
import re
import json
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from flask import Flask, render_template, request, jsonify, send_file, make_response

from invoice_templates import build_invoice, money_amount, money, money_in_words

APP_NAME = "SC Solutions"
CENT = Decimal("0.01")
ZERO = Decimal("0.00")

GST_VALUES = ["0%", "5%", "12%", "18%", "28%"]
UNIT_TYPES = ["Split Unit", "Cassette Unit", "Ductable Unit", "Resale"]
WORK_TYPES = [
    "Service", "Maintenance", "Installation", "Repair",
    "Gas Charging", "PCB Replacement", "Resale",
]

DEFAULT_TERMS = [
    "Payment due as agreed.",
    "Warranty as per company policy.",
    "Customer should provide safe access, electricity, water and working space.",
    "Any additional work, material, gas, spares or parts will be charged separately.",
    "Resale items warranty as per product condition and company policy.",
]

DEFAULT_COMPANY = {
    "company_name": "SC Solutions",
    "address": "Your address line 1\nYour address line 2\nBangalore, Karnataka, India - 000000",
    "gst": "", "pan": "", "phone": "+91 00000 00000",
    "default_gst": "18%",
    "terms": list(DEFAULT_TERMS),
}

SUGGESTED_ITEMS = {
    "Split Unit": {
        "Service": [
            {"area": "Split AC", "description": "General service - Split AC", "gst": "18%", "qty": "1", "rate": "1200"},
            {"area": "Split AC", "description": "Jet pump cleaning", "gst": "18%", "qty": "1", "rate": "500"},
            {"area": "Split AC", "description": "Gas pressure check", "gst": "18%", "qty": "1", "rate": "300"},
            {"area": "Split AC", "description": "Electrical terminal check", "gst": "18%", "qty": "1", "rate": "250"},
            {"area": "Split AC", "description": "Test run and performance check", "gst": "18%", "qty": "1", "rate": "300"},
        ],
        "Repair": [
            {"area": "Split AC", "description": "PCB replacement", "gst": "18%", "qty": "1", "rate": "2500"},
            {"area": "Split AC", "description": "Capacitor replacement", "gst": "18%", "qty": "1", "rate": "650"},
            {"area": "Split AC", "description": "Gas leakage repair labour", "gst": "18%", "qty": "1", "rate": "800"},
        ],
        "Installation": [
            {"area": "Split AC", "description": "New installation labour", "gst": "18%", "qty": "1", "rate": "1500"},
            {"area": "Split AC", "description": "Copper pipe per ft", "gst": "18%", "qty": "10", "rate": "750"},
            {"area": "Split AC", "description": "Outdoor unit stand", "gst": "18%", "qty": "1", "rate": "900"},
        ],
    },
    "Cassette Unit": {
        "Service": [
            {"area": "Cassette AC", "description": "Cassette AC general service", "gst": "18%", "qty": "1", "rate": "1800"},
            {"area": "Cassette AC", "description": "Indoor coil and filter cleaning", "gst": "18%", "qty": "1", "rate": "900"},
            {"area": "Cassette AC", "description": "Blower cleaning", "gst": "18%", "qty": "1", "rate": "700"},
            {"area": "Cassette AC", "description": "Condensate drain cleaning", "gst": "18%", "qty": "1", "rate": "500"},
            {"area": "Cassette AC", "description": "Gas pressure check", "gst": "18%", "qty": "1", "rate": "300"},
        ],
        "Repair": [
            {"area": "Cassette AC", "description": "Drain pump replacement", "gst": "18%", "qty": "1", "rate": "1800"},
            {"area": "Cassette AC", "description": "PCB replacement", "gst": "18%", "qty": "1", "rate": "3500"},
            {"area": "Cassette AC", "description": "Blower motor replacement", "gst": "18%", "qty": "1", "rate": "2200"},
        ],
    },
    "Ductable Unit": {
        "Service": [
            {"area": "Ductable AC", "description": "Ductable AC general service", "gst": "18%", "qty": "1", "rate": "2500"},
            {"area": "Ductable AC", "description": "Indoor coil/filter cleaning", "gst": "18%", "qty": "1", "rate": "1000"},
            {"area": "Ductable AC", "description": "Blower/fan cleaning", "gst": "18%", "qty": "1", "rate": "700"},
            {"area": "Ductable AC", "description": "Condensate drain cleaning", "gst": "18%", "qty": "1", "rate": "500"},
            {"area": "Ductable AC", "description": "Gas pressure check", "gst": "18%", "qty": "1", "rate": "300"},
        ],
        "Repair": [
            {"area": "Ductable AC", "description": "Duct leakage repair", "gst": "18%", "qty": "1", "rate": "1500"},
            {"area": "Ductable AC", "description": "Fan motor replacement", "gst": "18%", "qty": "1", "rate": "3000"},
            {"area": "Ductable AC", "description": "PCB replacement", "gst": "18%", "qty": "1", "rate": "4500"},
        ],
    },
    "Resale": {
        "Resale": [
            {"area": "Resale", "description": "Used Split AC 1 Ton", "gst": "18%", "qty": "1", "rate": "12000"},
            {"area": "Resale", "description": "Used Split AC 1.5 Ton", "gst": "18%", "qty": "1", "rate": "18000"},
            {"area": "Resale", "description": "Cassette AC indoor unit", "gst": "18%", "qty": "1", "rate": "22000"},
            {"area": "Resale", "description": "Ductable AC unit", "gst": "18%", "qty": "1", "rate": "35000"},
            {"area": "Resale", "description": "AC remote", "gst": "18%", "qty": "1", "rate": "800"},
            {"area": "Resale", "description": "Capacitor", "gst": "18%", "qty": "1", "rate": "450"},
            {"area": "Resale", "description": "PCB board", "gst": "18%", "qty": "1", "rate": "2500"},
            {"area": "Resale", "description": "Copper pipe per ft", "gst": "18%", "qty": "10", "rate": "750"},
        ]
    },
}

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
STORE_FILE = os.path.join(DATA_DIR, "sc_solutions_store.json")
PDF_DIR = os.path.join(DATA_DIR, "invoices")
os.makedirs(PDF_DIR, exist_ok=True)


def load_store():
    try:
        with open(STORE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}


def save_store(data):
    with open(STORE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_company_settings():
    data = dict(DEFAULT_COMPANY)
    data["terms"] = list(DEFAULT_TERMS)
    store = load_store()
    saved = store.get("company", {})
    if saved:
        data.update(saved)
        if "terms" not in saved:
            data["terms"] = list(DEFAULT_TERMS)
    return data


def save_company_settings(company):
    store = load_store()
    store["company"] = company
    save_store(store)


def next_invoice_no():
    store = load_store()
    year = date.today().year
    counter = store.get("invoice_counter", {}).get("num", 0)
    next_num = int(counter or 0) + 1
    return f"SC-{year}-{next_num:04d}"


def remember_invoice_no(invoice_no):
    store = load_store()
    match = re.search(r"(\d+)$", str(invoice_no))
    if match:
        store["invoice_counter"] = {"num": int(match.group(1))}
    save_store(store)


def add_history_record(data, path):
    store = load_store()
    record = {
        "invoice_no": data["invoice_no"],
        "customer_name": data["customer_name"],
        "invoice_date": data["invoice_date"],
        "total": money(data["grand_total"]),
        "path": path,
    }
    history = store.get("history", [])
    if not isinstance(history, list):
        history = []
    history.insert(0, record)
    store["history"] = history[:100]
    save_store(store)


def get_history():
    store = load_store()
    history = store.get("history", [])
    if not isinstance(history, list):
        return []
    return history


def safe_filename(text):
    text = re.sub(r"[^A-Za-z0-9_-]+", "-", str(text or "item").lower()).strip("-")
    return text[:60] or "item"


app = Flask(__name__)
app.secret_key = "sc_solutions_invoice_app"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        data = request.get_json()
        save_company_settings(data)
        return jsonify({"success": True})
    return jsonify(get_company_settings())


@app.route("/api/suggestions")
def suggestions():
    unit = request.args.get("unit", "Split Unit")
    work = request.args.get("work", "Service")
    items = SUGGESTED_ITEMS.get(unit, {}).get(work, [])
    if not items:
        items = SUGGESTED_ITEMS.get(unit, {}).get("Service", [])
    return jsonify(items)


@app.route("/api/history")
def history():
    return jsonify(get_history())


@app.route("/api/invoice-number")
def invoice_number():
    return jsonify({"number": next_invoice_no()})


@app.route("/api/generate", methods=["POST"])
def generate_invoice():
    data = request.get_json()
    company = get_company_settings()
    items = data.get("items", [])
    if not items:
        return jsonify({"error": "Please add at least one item"}), 400
    if not data.get("customer_name", "").strip():
        return jsonify({"error": "Please enter customer name"}), 400

    subtotal = ZERO
    cgst_total = ZERO
    sgst_total = ZERO
    for item in items:
        qty = money_amount(item.get("qty", "0"))
        rate = money_amount(item.get("rate", "0"))
        if qty <= 0 or rate < 0:
            continue
        try:
            gst_pct = Decimal(item.get("gst", "0%").replace("%", "").strip() or "0")
        except:
            gst_pct = Decimal("0")
        amount = (qty * rate).quantize(CENT, rounding=ROUND_HALF_UP)
        cgst = (amount * gst_pct / Decimal("100") / Decimal("2")).quantize(CENT, rounding=ROUND_HALF_UP)
        sgst = (amount * gst_pct / Decimal("100") / Decimal("2")).quantize(CENT, rounding=ROUND_HALF_UP)
        item["amount"] = float(amount)
        item["cgst"] = float(cgst)
        item["sgst"] = float(sgst)
        item["total"] = float(amount + cgst + sgst)
        subtotal += amount
        cgst_total += cgst
        sgst_total += sgst

    discount = money_amount(data.get("discount", "0"))
    before_discount = subtotal + cgst_total + sgst_total
    if discount > before_discount:
        return jsonify({"error": "Discount cannot be greater than subtotal plus tax"}), 400
    grand_total = before_discount - discount

    invoice_data = {
        "company_name": company.get("company_name", APP_NAME),
        "company_address": company.get("address", ""),
        "gst": company.get("gst", ""),
        "pan": company.get("pan", ""),
        "phone": company.get("phone", ""),
        "invoice_no": data.get("invoice_no", "").strip() or next_invoice_no(),
        "invoice_date": data.get("invoice_date", "").strip() or date.today().strftime("%d-%m-%Y"),
        "payment_status": data.get("payment_status", "Unpaid"),
        "customer_name": data["customer_name"].strip(),
        "customer_phone": data.get("customer_phone", "").strip(),
        "customer_address": data.get("customer_address", "").strip(),
        "unit_type": data.get("unit_type", "Split Unit"),
        "work_type": data.get("work_type", "Service"),
        "items": items,
        "subtotal": float(subtotal),
        "cgst_total": float(cgst_total),
        "sgst_total": float(sgst_total),
        "discount": float(discount),
        "grand_total": float(grand_total),
        "amount_in_words": money_in_words(grand_total),
        "terms": company.get("terms", DEFAULT_TERMS),
    }

    template = data.get("template", "A")
    filename = f"invoice-{safe_filename(invoice_data['invoice_no'])}-{safe_filename(invoice_data['customer_name'])}-{safe_filename(invoice_data['unit_type'])}.pdf"
    filepath = os.path.join(PDF_DIR, filename)
    build_invoice(invoice_data, filepath, template=template)
    remember_invoice_no(invoice_data["invoice_no"])
    add_history_record(invoice_data, filepath)

    return jsonify({"success": True, "filename": filename, "download_url": f"/download/{filename}"})


@app.route("/download/<filename>")
def download(filename):
    filepath = os.path.join(PDF_DIR, filename)
    if not os.path.exists(filepath):
        return "File not found", 404
    return send_file(filepath, as_attachment=True, download_name=filename)


@app.route("/api/invoice/<filename>")
def view_invoice(filename):
    filepath = os.path.join(PDF_DIR, filename)
    if not os.path.exists(filepath):
        return "File not found", 404
    return send_file(filepath, mimetype="application/pdf")


@app.route("/api/calculate", methods=["POST"])
def calculate():
    data = request.get_json()
    items = data.get("items", [])
    subtotal = ZERO
    tax = ZERO
    for item in items:
        qty = money_amount(item.get("qty", "0"))
        rate = money_amount(item.get("rate", "0"))
        if qty <= 0 or rate < 0:
            continue
        try:
            gst_pct = Decimal(item.get("gst", "0%").replace("%", "").strip() or "0")
        except:
            gst_pct = Decimal("0")
        amount = (qty * rate).quantize(CENT, rounding=ROUND_HALF_UP)
        cgst = (amount * gst_pct / Decimal("100") / Decimal("2")).quantize(CENT, rounding=ROUND_HALF_UP)
        sgst = (amount * gst_pct / Decimal("100") / Decimal("2")).quantize(CENT, rounding=ROUND_HALF_UP)
        subtotal += amount
        tax += cgst + sgst
    return jsonify({"subtotal": money(subtotal), "tax": money(tax), "total": money(subtotal + tax)})


@app.route("/api/print/<filename>")
def print_invoice(filename):
    filepath = os.path.join(PDF_DIR, filename)
    if not os.path.exists(filepath):
        return "File not found", 404
    response = make_response(send_file(filepath, mimetype="application/pdf"))
    response.headers["Content-Disposition"] = f"inline; filename={filename}"
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
