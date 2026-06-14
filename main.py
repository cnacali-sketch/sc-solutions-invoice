import os
import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from kivy.app import App
from kivy.metrics import dp
from kivy.storage.jsonstore import JsonStore
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton

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
            ("Split AC", "General service - Split AC", "18%", "1", "1200"),
            ("Split AC", "Jet pump cleaning", "18%", "1", "500"),
            ("Split AC", "Gas pressure check", "18%", "1", "300"),
            ("Split AC", "Electrical terminal check", "18%", "1", "250"),
            ("Split AC", "Test run and performance check", "18%", "1", "300"),
        ],
        "Repair": [
            ("Split AC", "PCB replacement", "18%", "1", "2500"),
            ("Split AC", "Capacitor replacement", "18%", "1", "650"),
            ("Split AC", "Gas leakage repair labour", "18%", "1", "800"),
        ],
        "Installation": [
            ("Split AC", "New installation labour", "18%", "1", "1500"),
            ("Split AC", "Copper pipe per ft", "18%", "10", "750"),
            ("Split AC", "Outdoor unit stand", "18%", "1", "900"),
        ],
    },
    "Cassette Unit": {
        "Service": [
            ("Cassette AC", "Cassette AC general service", "18%", "1", "1800"),
            ("Cassette AC", "Indoor coil and filter cleaning", "18%", "1", "900"),
            ("Cassette AC", "Blower cleaning", "18%", "1", "700"),
            ("Cassette AC", "Condensate drain cleaning", "18%", "1", "500"),
            ("Cassette AC", "Gas pressure check", "18%", "1", "300"),
        ],
        "Repair": [
            ("Cassette AC", "Drain pump replacement", "18%", "1", "1800"),
            ("Cassette AC", "PCB replacement", "18%", "1", "3500"),
            ("Cassette AC", "Blower motor replacement", "18%", "1", "2200"),
        ],
    },
    "Ductable Unit": {
        "Service": [
            ("Ductable AC", "Ductable AC general service", "18%", "1", "2500"),
            ("Ductable AC", "Indoor coil/filter cleaning", "18%", "1", "1000"),
            ("Ductable AC", "Blower/fan cleaning", "18%", "1", "700"),
            ("Ductable AC", "Condensate drain cleaning", "18%", "1", "500"),
            ("Ductable AC", "Gas pressure check", "18%", "1", "300"),
        ],
        "Repair": [
            ("Ductable AC", "Duct leakage repair", "18%", "1", "1500"),
            ("Ductable AC", "Fan motor replacement", "18%", "1", "3000"),
            ("Ductable AC", "PCB replacement", "18%", "1", "4500"),
        ],
    },
    "Resale": {
        "Resale": [
            ("Resale", "Used Split AC 1 Ton", "18%", "1", "12000"),
            ("Resale", "Used Split AC 1.5 Ton", "18%", "1", "18000"),
            ("Resale", "Cassette AC indoor unit", "18%", "1", "22000"),
            ("Resale", "Ductable AC unit", "18%", "1", "35000"),
            ("Resale", "AC remote", "18%", "1", "800"),
            ("Resale", "Capacitor", "18%", "1", "450"),
            ("Resale", "PCB board", "18%", "1", "2500"),
            ("Resale", "Copper pipe per ft", "18%", "10", "750"),
        ]
    },
}


def safe_filename(text):
    text = re.sub(r"[^A-Za-z0-9_-]+", "-", str(text or "item").lower()).strip("-")
    return text[:60] or "item"


def show_message(title, message):
    content = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
    label = Label(text=message, halign="left", valign="top")
    label.bind(size=label.setter("text_size"))
    ok = Button(text="OK", size_hint_y=None, height=dp(40))
    popup = Popup(title=title, content=content, size_hint=(0.9, 0.35))
    ok.bind(on_press=lambda *args: popup.dismiss())
    content.add_widget(label)
    content.add_widget(ok)
    popup.open()


class FormRow(BoxLayout):
    def __init__(self, label_text, widget, label_width=0.28, row_height=dp(42), **kwargs):
        super().__init__(
            orientation="horizontal", size_hint_y=None, height=row_height,
            spacing=dp(6), **kwargs,
        )
        label = Label(text=label_text, size_hint_x=label_width, bold=True,
                      halign="left", valign="middle")
        label.bind(size=label.setter("text_size"))
        self.add_widget(label)
        self.add_widget(widget)


class SectionTitle(Label):
    def __init__(self, text, **kwargs):
        super().__init__(
            text=text, size_hint_y=None, height=dp(30),
            bold=True, color=(0.08, 0.25, 0.45, 1),
            halign="left", valign="middle", **kwargs,
        )
        self.bind(size=self.setter("text_size"))


class InvoiceItemRow(BoxLayout):
    def __init__(self, item=None, screen=None, **kwargs):
        item = item or {}
        super().__init__(
            orientation="horizontal", size_hint_y=None, height=dp(54),
            spacing=dp(4), **kwargs,
        )
        self.screen = screen
        self.description = TextInput(
            text=item.get("description", ""), hint_text="Description", multiline=False)
        self.area = TextInput(
            text=item.get("area", ""), hint_text="Area", multiline=False)
        self.gst = Spinner(text=item.get("gst", "18%"), values=GST_VALUES, size_hint_x=0.12)
        self.qty = TextInput(
            text=str(item.get("qty", "1")), hint_text="Qty", input_filter="float",
            multiline=False, size_hint_x=0.10)
        self.rate = TextInput(
            text=str(item.get("rate", "")), hint_text="Rate", input_filter="float",
            multiline=False, size_hint_x=0.12)
        remove_btn = Button(text="Remove", size_hint_x=0.12)
        remove_btn.bind(on_press=self.remove_row)
        self.add_widget(self.description)
        self.add_widget(self.area)
        self.add_widget(self.gst)
        self.add_widget(self.qty)
        self.add_widget(self.rate)
        self.add_widget(remove_btn)

    def remove_row(self, *args):
        if self.screen:
            self.screen.remove_item_row(self)


class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        title = Label(
            text="SC Solutions", size_hint_y=None, height=dp(72),
            font_size=dp(34), bold=True, halign="center", valign="middle")
        title.bind(size=title.setter("text_size"))
        subtitle = Label(
            text="AC Service, Repair, Installation and Resale Invoice App",
            size_hint_y=None, height=dp(42), font_size=dp(15), halign="center", valign="middle")
        subtitle.bind(size=subtitle.setter("text_size"))
        root.add_widget(title)
        root.add_widget(subtitle)
        root.add_widget(Label(text="", size_hint_y=None, height=dp(20)))
        buttons = [
            ("New Invoice", "invoice"),
            ("Suggested Items", "catalog"),
            ("Invoice History", "history"),
            ("Settings", "settings"),
        ]
        for text, target in buttons:
            btn = Button(text=text, size_hint_y=None, height=dp(54), font_size=dp(17))
            btn.bind(on_press=lambda *args, target=target: setattr(self.manager, "current", target))
            root.add_widget(btn)
        self.add_widget(root)


class InvoiceScreen(Screen):
    def __init__(self, invoice_app=None, **kwargs):
        super().__init__(**kwargs)
        self.invoice_app = invoice_app
        self.item_rows = []
        self.selected_template = "A"
        self.build_ui()

    def build_ui(self):
        app = self.invoice_app
        company = app.get_company_settings()
        default_gst = company.get("default_gst", "18%")
        if default_gst not in GST_VALUES:
            default_gst = "18%"

        root = GridLayout(cols=1, size_hint_y=None, padding=dp(10), spacing=dp(8))
        root.bind(minimum_height=root.setter("height"))
        scroll = ScrollView()
        scroll.add_widget(root)
        self.add_widget(scroll)

        root.add_widget(Label(
            text="Create Invoice", size_hint_y=None, height=dp(38),
            bold=True, font_size=dp(20), halign="center"))

        self.invoice_no = TextInput(text=app.next_invoice_no(), multiline=False, hint_text="Invoice No")
        self.invoice_date = TextInput(
            text=date.today().strftime("%d-%m-%Y"), multiline=False, hint_text="Invoice Date")
        self.payment_status = Spinner(
            text="Unpaid", values=["Paid", "Unpaid", "Advance Received"],
            size_hint_y=None, height=dp(40))

        root.add_widget(SectionTitle("Invoice Details"))
        root.add_widget(FormRow("Invoice No #", self.invoice_no))
        root.add_widget(FormRow("Invoice Date", self.invoice_date))
        root.add_widget(FormRow("Payment Status", self.payment_status))

        self.customer_name = TextInput(text="", multiline=False, hint_text="Customer Name")
        self.customer_phone = TextInput(text="", multiline=False, hint_text="Customer Phone")
        self.customer_address = TextInput(text="", multiline=True, hint_text="Customer Address")
        root.add_widget(SectionTitle("Customer Details"))
        root.add_widget(FormRow("Customer Name", self.customer_name))
        root.add_widget(FormRow("Phone", self.customer_phone))
        root.add_widget(FormRow("Address", self.customer_address, row_height=dp(72)))

        self.unit_type = Spinner(
            text="Split Unit", values=UNIT_TYPES, size_hint_y=None, height=dp(40))
        self.work_type = Spinner(
            text="Service", values=WORK_TYPES, size_hint_y=None, height=dp(40))
        self.gst_default = Spinner(
            text=default_gst, values=GST_VALUES, size_hint_y=None, height=dp(40))
        root.add_widget(SectionTitle("Job / Product Details"))
        root.add_widget(FormRow("Unit Type", self.unit_type))
        root.add_widget(FormRow("Work Type", self.work_type))
        root.add_widget(FormRow("Default GST", self.gst_default))

        root.add_widget(SectionTitle("Template Style"))
        template_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(42), spacing=dp(8))
        self.template_buttons = {}
        for label, value in [("Professional", "A"), ("Modern", "B"), ("Classic", "C")]:
            btn = ToggleButton(text=label, group="template", size_hint_x=1/3)
            btn.template_value = value
            btn.bind(on_press=lambda *args, v=value: self.set_template(v))
            self.template_buttons[value] = btn
            template_row.add_widget(btn)
        self.template_buttons["A"].state = "down"
        root.add_widget(template_row)

        root.add_widget(SectionTitle("Items"))
        root.add_widget(Label(
            text="Description | Area | GST | Qty | Rate",
            size_hint_y=None, height=dp(28), italic=True, color=(0.2, 0.2, 0.2, 1)))

        button_row = BoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(46), spacing=dp(8))
        suggested_btn = Button(text="Add Suggested")
        suggested_btn.bind(on_press=self.show_suggestions)
        custom_btn = Button(text="Add Custom")
        custom_btn.bind(on_press=self.add_custom_item)
        clear_btn = Button(text="Clear")
        clear_btn.bind(on_press=self.clear_items)
        button_row.add_widget(suggested_btn)
        button_row.add_widget(custom_btn)
        button_row.add_widget(clear_btn)
        root.add_widget(button_row)

        self.item_container = GridLayout(cols=1, size_hint_y=None, spacing=dp(3))
        self.item_container.bind(minimum_height=self.item_container.setter("height"))
        root.add_widget(self.item_container)

        self.total_label = Label(
            text="Total: Rs. 0.00", size_hint_y=None, height=dp(38),
            bold=True, color=(0.05, 0.35, 0.15, 1), halign="left")
        self.total_label.bind(size=self.total_label.setter("text_size"))
        root.add_widget(self.total_label)

        self.discount = TextInput(
            text="0", hint_text="Discount", input_filter="float", multiline=False)
        root.add_widget(FormRow("Discount Amount", self.discount))

        generate_btn = Button(
            text="Generate PDF Invoice", size_hint_y=None, height=dp(54), font_size=dp(17))
        generate_btn.bind(on_press=self.generate_pdf)
        root.add_widget(generate_btn)

        back_btn = Button(text="Back Home", size_hint_y=None, height=dp(46))
        back_btn.bind(on_press=lambda *args: setattr(self.manager, "current", "home"))
        root.add_widget(back_btn)

    def set_template(self, value):
        self.selected_template = value

    def add_custom_item(self, *args):
        item = {
            "area": self.unit_type.text, "description": "",
            "gst": self.gst_default.text, "qty": "1", "rate": "",
        }
        self.add_item_row(item)

    def add_item_row(self, item):
        row = InvoiceItemRow(item=item, screen=self)
        self.item_rows.append(row)
        self.item_container.add_widget(row)
        self.update_total()

    def remove_item_row(self, row):
        if row in self.item_rows:
            self.item_rows.remove(row)
            self.item_container.remove_widget(row)
            self.update_total()

    def clear_items(self, *args):
        for row in list(self.item_rows):
            self.item_container.remove_widget(row)
        self.item_rows.clear()
        self.update_total()

    def collect_items(self):
        items = []
        for row in self.item_rows:
            description = row.description.text.strip()
            if not description:
                continue
            qty = money_amount(row.qty.text)
            rate = money_amount(row.rate.text)
            if qty <= 0 or rate < 0:
                continue
            try:
                gst_pct = Decimal(row.gst.text.replace("%", "").strip() or "0")
            except Exception:
                gst_pct = Decimal("0")
            amount = (qty * rate).quantize(CENT, rounding=ROUND_HALF_UP)
            cgst = (amount * gst_pct / Decimal("100") / Decimal("2")).quantize(CENT, rounding=ROUND_HALF_UP)
            sgst = (amount * gst_pct / Decimal("100") / Decimal("2")).quantize(CENT, rounding=ROUND_HALF_UP)
            total = (amount + cgst + sgst).quantize(CENT, rounding=ROUND_HALF_UP)
            items.append({
                "area": row.area.text.strip() or self.unit_type.text,
                "description": description, "gst": row.gst.text,
                "qty": qty, "rate": rate,
                "amount": amount, "cgst": cgst, "sgst": sgst, "total": total,
            })
        return items

    def update_total(self):
        items = self.collect_items()
        subtotal = sum((money_amount(item["amount"]) for item in items), ZERO)
        tax = sum(
            (money_amount(item["cgst"]) + money_amount(item["sgst"]) for item in items),
            ZERO,
        )
        self.total_label.text = f"Subtotal {money(subtotal)} | Tax {money(tax)} | Total {money(subtotal + tax)}"

    def show_suggestions(self, *args):
        unit = self.unit_type.text
        work = self.work_type.text
        suggestions = SUGGESTED_ITEMS.get(unit, {}).get(work, [])
        if not suggestions:
            suggestions = SUGGESTED_ITEMS.get(unit, {}).get("Service", [])
        content = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        grid = GridLayout(cols=1, size_hint_y=None, spacing=dp(6))
        grid.bind(minimum_height=grid.setter("height"))
        scroll = ScrollView()
        scroll.add_widget(grid)
        if not suggestions:
            grid.add_widget(Label(text="No suggestions found.", size_hint_y=None, height=dp(40)))
        else:
            for area, desc, gst, qty, rate in suggestions:
                item = {"area": area, "description": desc, "gst": gst, "qty": qty, "rate": rate}
                btn = Button(
                    text=f"{desc}\n{area} | GST {gst} | Qty {fmt_decimal(qty)} | Rate {money(rate)}",
                    size_hint_y=None, height=dp(58), halign="left")
                btn.bind(size=btn.setter("text_size"))
                btn.bind(on_press=lambda *args, item=item: self.add_item_row(item))
                grid.add_widget(btn)
        close = Button(text="Close", size_hint_y=None, height=dp(42))
        popup = Popup(title="Suggested Items", content=content, size_hint=(0.95, 0.8))
        close.bind(on_press=lambda *args: popup.dismiss())
        content.add_widget(scroll)
        content.add_widget(close)
        popup.open()

    def make_pdf_path(self, data):
        folder = "/sdcard/Download"
        if not os.path.isdir(folder):
            folder = os.path.expanduser("~")
        filename = f"invoice-{safe_filename(data['invoice_no'])}-{safe_filename(data['customer_name'])}-{safe_filename(data['unit_type'])}.pdf"
        return os.path.join(folder, filename)

    def generate_pdf(self, *args):
        items = self.collect_items()
        if not items:
            show_message("Add Items", "Please add at least one invoice item.")
            return
        customer_name = self.customer_name.text.strip()
        if not customer_name:
            show_message("Customer Required", "Please enter customer name.")
            return
        company = self.invoice_app.get_company_settings()
        subtotal = sum((money_amount(item["amount"]) for item in items), ZERO)
        cgst_total = sum((money_amount(item["cgst"]) for item in items), ZERO)
        sgst_total = sum((money_amount(item["sgst"]) for item in items), ZERO)
        discount = money_amount(self.discount.text)
        before_discount = subtotal + cgst_total + sgst_total
        if discount > before_discount:
            show_message("Invalid Discount", "Discount cannot be greater than subtotal plus tax.")
            return
        grand_total = before_discount - discount

        data = {
            "company_name": company.get("company_name", APP_NAME),
            "company_address": company.get("address", ""),
            "gst": company.get("gst", ""),
            "pan": company.get("pan", ""),
            "phone": company.get("phone", ""),
            "invoice_no": self.invoice_no.text.strip() or self.invoice_app.next_invoice_no(),
            "invoice_date": self.invoice_date.text.strip() or date.today().strftime("%d-%m-%Y"),
            "payment_status": self.payment_status.text,
            "customer_name": customer_name,
            "customer_phone": self.customer_phone.text.strip(),
            "customer_address": self.customer_address.text.strip(),
            "unit_type": self.unit_type.text,
            "work_type": self.work_type.text,
            "items": items,
            "subtotal": subtotal,
            "cgst_total": cgst_total,
            "sgst_total": sgst_total,
            "discount": discount,
            "grand_total": grand_total,
            "amount_in_words": money_in_words(grand_total),
            "terms": company.get("terms", DEFAULT_TERMS),
        }
        path = self.make_pdf_path(data)
        try:
            build_invoice(data, path, template=self.selected_template)
            self.invoice_app.remember_invoice_no(data["invoice_no"])
            self.invoice_app.add_history_record(data, path)
            show_message("PDF Saved", f"Invoice saved to:\n{path}")
        except Exception as exc:
            show_message("PDF Error", str(exc))


class CatalogScreen(Screen):
    def __init__(self, invoice_app=None, **kwargs):
        super().__init__(**kwargs)
        self.invoice_app = invoice_app
        root = GridLayout(cols=1, size_hint_y=None, padding=dp(10), spacing=dp(8))
        root.bind(minimum_height=root.setter("height"))
        title = Label(
            text="Suggested Items", size_hint_y=None, height=dp(40),
            bold=True, font_size=dp(22), halign="center")
        title.bind(size=title.setter("text_size"))
        self.unit_spinner = Spinner(
            text="Split Unit", values=UNIT_TYPES, size_hint_y=None, height=dp(42))
        self.catalog_container = GridLayout(cols=1, size_hint_y=None, spacing=dp(6))
        self.catalog_container.bind(minimum_height=self.catalog_container.setter("height"))
        scroll = ScrollView()
        scroll.add_widget(self.catalog_container)
        back = Button(text="Back Home", size_hint_y=None, height=dp(46))
        back.bind(on_press=lambda *args: setattr(self.manager, "current", "home"))
        root.add_widget(title)
        root.add_widget(Label(text="Select unit type:", size_hint_y=None, height=dp(28)))
        root.add_widget(self.unit_spinner)
        root.add_widget(scroll)
        root.add_widget(back)
        self.add_widget(root)
        self.unit_spinner.bind(text=self.refresh_catalog)
        self.refresh_catalog()

    def refresh_catalog(self, *args):
        self.catalog_container.clear_widgets()
        unit = self.unit_spinner.text
        catalog = SUGGESTED_ITEMS.get(unit, {})
        if not catalog:
            self.catalog_container.add_widget(
                Label(text="No catalog available.", size_hint_y=None, height=dp(50)))
            return
        for work_type, items in catalog.items():
            self.catalog_container.add_widget(SectionTitle(work_type))
            for area, desc, gst, qty, rate in items:
                item = {"area": area, "description": desc, "gst": gst, "qty": qty, "rate": rate}
                btn = Button(
                    text=f"{desc}\n{area} | GST {gst} | Qty {fmt_decimal(qty)} | Rate {money(rate)}",
                    size_hint_y=None, height=dp(60), halign="left")
                btn.bind(size=btn.setter("text_size"))
                btn.bind(on_press=lambda *args, item=item: self.add_to_invoice(item))
                self.catalog_container.add_widget(btn)

    def add_to_invoice(self, item):
        invoice_screen = self.manager.get_screen("invoice")
        invoice_screen.add_item_row(item)
        self.manager.current = "invoice"


class SettingsScreen(Screen):
    def __init__(self, invoice_app=None, **kwargs):
        super().__init__(**kwargs)
        self.invoice_app = invoice_app
        self.fields = {}
        self.build_ui()

    def build_ui(self):
        root = GridLayout(cols=1, size_hint_y=None, padding=dp(10), spacing=dp(8))
        root.bind(minimum_height=root.setter("height"))
        scroll = ScrollView()
        scroll.add_widget(root)
        self.add_widget(scroll)
        root.add_widget(Label(
            text="Settings", size_hint_y=None, height=dp(40),
            bold=True, font_size=dp(22), halign="center"))
        labels = [
            ("Company Name", "company_name"),
            ("Address", "address"),
            ("GSTIN", "gst"),
            ("PAN", "pan"),
            ("Phone", "phone"),
            ("Default GST", "default_gst"),
        ]
        for label_text, key in labels:
            multiline = key == "address"
            widget = TextInput(text="", multiline=multiline)
            self.fields[key] = widget
            root.add_widget(FormRow(label_text, widget, row_height=dp(72) if multiline else dp(42)))
        root.add_widget(Label(
            text="Terms & Conditions (one per line)", size_hint_y=None, height=dp(30)))
        self.terms_input = TextInput(
            text="", multiline=True, size_hint_y=None, height=dp(170))
        root.add_widget(self.terms_input)
        save_btn = Button(text="Save Settings", size_hint_y=None, height=dp(50))
        save_btn.bind(on_press=self.save_settings)
        root.add_widget(save_btn)
        back_btn = Button(text="Back Home", size_hint_y=None, height=dp(46))
        back_btn.bind(on_press=lambda *args: setattr(self.manager, "current", "home"))
        root.add_widget(back_btn)
        self.load_settings()

    def load_settings(self):
        company = self.invoice_app.get_company_settings()
        for key, field in self.fields.items():
            field.text = str(company.get(key, ""))
        terms = company.get("terms", DEFAULT_TERMS)
        if isinstance(terms, str):
            terms = terms.splitlines()
        self.terms_input.text = "\n".join(terms)

    def save_settings(self, *args):
        company = {key: field.text.strip() for key, field in self.fields.items()}
        terms = [line.strip() for line in self.terms_input.text.splitlines() if line.strip()]
        if not terms:
            terms = list(DEFAULT_TERMS)
        company["terms"] = terms
        self.invoice_app.save_company_settings(company)
        show_message("Saved", "Settings saved locally.")


class HistoryScreen(Screen):
    def __init__(self, invoice_app=None, **kwargs):
        super().__init__(**kwargs)
        self.invoice_app = invoice_app
        root = GridLayout(cols=1, size_hint_y=None, padding=dp(10), spacing=dp(8))
        root.bind(minimum_height=root.setter("height"))
        title = Label(
            text="Invoice History", size_hint_y=None, height=dp(40),
            bold=True, font_size=dp(22), halign="center")
        title.bind(size=title.setter("text_size"))
        refresh = Button(text="Refresh", size_hint_y=None, height=dp(42))
        refresh.bind(on_press=self.refresh_history)
        self.history_container = GridLayout(cols=1, size_hint_y=None, spacing=dp(6))
        self.history_container.bind(minimum_height=self.history_container.setter("height"))
        scroll = ScrollView()
        scroll.add_widget(self.history_container)
        back = Button(text="Back Home", size_hint_y=None, height=dp(46))
        back.bind(on_press=lambda *args: setattr(self.manager, "current", "home"))
        root.add_widget(title)
        root.add_widget(refresh)
        root.add_widget(scroll)
        root.add_widget(back)
        self.add_widget(root)

    def on_enter(self):
        self.refresh_history()

    def refresh_history(self, *args):
        self.history_container.clear_widgets()
        history = self.invoice_app.get_history()
        if not history:
            self.history_container.add_widget(
                Label(text="No invoices yet.", size_hint_y=None, height=dp(60)))
            return
        for rec in history[:50]:
            box = BoxLayout(
                orientation="vertical", size_hint_y=None, height=dp(82), spacing=dp(4))
            text = f"{rec.get('invoice_no', '')} | {rec.get('customer_name', '')} | {rec.get('invoice_date', '')} | Total {rec.get('total', '')}"
            label = Label(text=text, size_hint_y=None, height=dp(46), halign="left", valign="middle")
            label.bind(size=label.setter("text_size"))
            btn = Button(text="Show Path", size_hint_y=None, height=dp(32))
            btn.bind(on_press=lambda *args, path=rec.get("path", ""): show_message("Saved Path", path))
            box.add_widget(label)
            box.add_widget(btn)
            self.history_container.add_widget(box)


class SCSolutionsApp(App):
    def build(self):
        self.store = JsonStore("sc_solutions_store.json")
        self.title = "SC Solutions"
        sm = ScreenManager()
        self.home = HomeScreen(name="home")
        self.invoice = InvoiceScreen(invoice_app=self, name="invoice")
        self.catalog = CatalogScreen(invoice_app=self, name="catalog")
        self.settings = SettingsScreen(invoice_app=self, name="settings")
        self.history = HistoryScreen(invoice_app=self, name="history")
        sm.add_widget(self.home)
        sm.add_widget(self.invoice)
        sm.add_widget(self.catalog)
        sm.add_widget(self.settings)
        sm.add_widget(self.history)
        return sm

    def get_company_settings(self):
        data = dict(DEFAULT_COMPANY)
        data["terms"] = list(DEFAULT_TERMS)
        try:
            saved = self.store.get("company", default={})
        except Exception:
            saved = {}
        if saved:
            data.update(saved)
            if "terms" not in saved:
                data["terms"] = list(DEFAULT_TERMS)
        return data

    def save_company_settings(self, company):
        self.store.put("company", **company)

    def next_invoice_no(self):
        year = date.today().year
        try:
            counter = self.store.get("invoice_counter", default={"num": 0}).get("num", 0)
        except Exception:
            counter = 0
        next_num = int(counter or 0) + 1
        return f"SC-{year}-{next_num:04d}"

    def remember_invoice_no(self, invoice_no):
        match = re.search(r"(\d+)$", str(invoice_no))
        if match:
            self.store.put("invoice_counter", num=int(match.group(1)))

    def add_history_record(self, data, path):
        record = {
            "invoice_no": data["invoice_no"],
            "customer_name": data["customer_name"],
            "invoice_date": data["invoice_date"],
            "total": money(data["grand_total"]),
            "path": path,
        }
        try:
            history = self.store.get("history", default=[])
        except Exception:
            history = []
        if not isinstance(history, list):
            history = []
        history.insert(0, record)
        self.store.put("history", history[:100])

    def get_history(self):
        try:
            history = self.store.get("history", default=[])
        except Exception:
            history = []
        if not isinstance(history, list):
            return []
        return history


if __name__ == "__main__":
    SCSolutionsApp().run()
