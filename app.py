import easyocr
from PIL import Image
import pdfplumber
import re
from flask import Flask, render_template, request, redirect
import sqlite3
import psycopg2
import psycopg2.extras
from datetime import date
import random
import os

app = Flask(__name__)

# ---------------------------------------
# USE POSTGRES ON RENDER
# ---------------------------------------
USE_POSTGRES = bool(os.environ.get("DATABASE_URL"))
DATABASE_URL = os.environ.get("DATABASE_URL")

# Initialize EasyOCR (English)
ocr_reader = easyocr.Reader(['en'], gpu=False)


def clean_number(value):
    """Clean OCR values."""
    if not value:
        return 0.0

    value = value.replace(",", "").replace("Rs", "").replace("₹", "")
    value = value.replace(":", "").replace(" ", "").replace("..", ".").strip()

    if value in ["", ".", ".."]:
        return 0.0

    try:
        return float(value)
    except:
        return 0.0


# ---------------------------------------
# DB CONNECTION
# ---------------------------------------
def get_db():
    if USE_POSTGRES:
        return psycopg2.connect(
            DATABASE_URL,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    else:
        conn = sqlite3.connect("database.db")
        conn.row_factory = sqlite3.Row
        return conn


# ---------------------------------------
# UNIVERSAL QUERY EXECUTOR
# ---------------------------------------
def db_execute(cur, query, params=None, fetch=False, many=False):
    if not USE_POSTGRES:
        query = query.replace("%s", "?")

    if params:
        if many:
            cur.executemany(query, params)
        else:
            cur.execute(query, params)
    else:
        cur.execute(query)

    if fetch:
        return cur.fetchall()
    return None


# ---------------------------------------
# INITIALIZE DB
# ---------------------------------------
def init_db():
    conn = get_db()
    cur = conn.cursor()

    db_execute(cur, """
        CREATE TABLE IF NOT EXISTS customers (
            id SERIAL PRIMARY KEY,
            name TEXT,
            phone TEXT
        );
    """)

    db_execute(cur, """
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name TEXT,
            price REAL
        );
    """)

    db_execute(cur, """
        CREATE TABLE IF NOT EXISTS bills (
            id SERIAL PRIMARY KEY,
            customer_id INTEGER,
            bill_date TEXT,
            total REAL
        );
    """)

    db_execute(cur, """
        CREATE TABLE IF NOT EXISTS bill_items (
            id SERIAL PRIMARY KEY,
            bill_id INTEGER,
            product_id INTEGER,
            price REAL,
            quantity REAL,
            item_total REAL
        );
    """)

    # TEMPORARY TABLE FOR INVOICE PROCESSING
    db_execute(cur, """
        CREATE TABLE IF NOT EXISTS invoice_items_temp (
            id SERIAL PRIMARY KEY,
            product_name TEXT,
            quantity REAL,
            price REAL,
            item_total REAL
        );
    """)

    conn.commit()
    cur.close()
    conn.close()


# ---------------------------------------
# SEED DATA
# ---------------------------------------
def seed_data():
    conn = get_db()
    cur = conn.cursor()

    existing = db_execute(cur, "SELECT COUNT(*) AS c FROM customers", fetch=True)[0]["c"]
    if existing > 0:
        return

    names = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Krishna", "Surya", "Lakshmi"]
    products = ["Onion", "Tomato", "Potato", "Carrot", "Spinach", "Milk", "Paneer", "Oil", "Soap"]

    for i in range(1, 51):
        name = random.choice(names) + str(i)
        phone = "9" + str(random.randint(100000000, 999999999))
        db_execute(cur, "INSERT INTO customers (name, phone) VALUES (%s, %s)", (name, phone))

    for p in products:
        price = random.randint(10, 200)
        db_execute(cur, "INSERT INTO products (name, price) VALUES (%s, %s)", (p, price))

    conn.commit()
    cur.close()
    conn.close()


with app.app_context():
    init_db()
    seed_data()


# ---------------------------------------
# HOME PAGE
# ---------------------------------------
@app.route("/")
def index():
    conn = get_db()
    cur = conn.cursor()

    search = request.args.get("search")

    query = """
        SELECT bills.id, bills.bill_date, bills.total,
               customers.id AS customer_id,
               customers.name AS customer_name
        FROM bills
        JOIN customers ON bills.customer_id = customers.id
    """

    if search:
        bills = db_execute(cur,
            query + " WHERE customers.name LIKE %s OR CAST(customers.id AS TEXT) LIKE %s ORDER BY bills.id DESC",
            (f"%{search}%", f"%{search}%"),
            fetch=True
        )
    else:
        bills = db_execute(cur, query + " ORDER BY bills.id DESC", fetch=True)

    bill_items = db_execute(cur, """
        SELECT bill_items.bill_id,
               products.name AS product_name,
               bill_items.price,
               bill_items.quantity,
               bill_items.item_total
        FROM bill_items
        JOIN products ON bill_items.product_id = products.id
    """, fetch=True)

    return render_template("index.html", bills=bills, bill_items=bill_items, search=search)


# ---------------------------------------
# PURCHASE SUMMARY (ONLY TEMP DATA)
# ---------------------------------------
@app.route("/purchase_summary")
def purchase_summary():
    conn = get_db()
    cur = conn.cursor()

    summary = db_execute(cur, """
        SELECT product_name,
               SUM(quantity) AS total_quantity,
               AVG(price) AS avg_price,
               SUM(item_total) AS total_amount
        FROM invoice_items_temp
        GROUP BY product_name
        ORDER BY product_name
    """, fetch=True)

    return render_template("purchase_summary.html", summary=summary)


# ---------------------------------------
# UPLOAD INVOICE
# ---------------------------------------
@app.route("/upload_invoice", methods=["GET", "POST"])
def upload_invoice():
    if request.method == "GET":
        return render_template("upload_invoice.html")

    uploaded_text = ""
    file = request.files.get("invoice_file")
    text_input = request.form.get("invoice_text", "").strip()

    # Text input
    if text_input:
        uploaded_text = text_input

    # File uploaded
    elif file and file.filename:
        os.makedirs("uploads", exist_ok=True)
        filepath = "uploads/" + file.filename
        file.save(filepath)

        if file.filename.lower().endswith(".pdf"):
            text = ""
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text += t + "\n"
            uploaded_text = text

        else:
            # EASY OCR for images
            result = ocr_reader.readtext(filepath, detail=0)
            uploaded_text = "\n".join(result)

    else:
        return "No input provided", 400

    # REGEX extraction
    pattern = r"""
        ^\d+\s+
        ([A-Za-z0-9 /]+)\s+
        ([\d\.]+)\s+
        [A-Za-z]+\s+
        Rs\.?\s*([\d\.]+)\s+
        Rs\.?\s*([\d\.]+)
    """

    items = re.findall(pattern, uploaded_text, re.MULTILINE | re.VERBOSE)

    if not items:
        return "Could not extract items"

    # Insert clean summary
    conn = get_db()
    cur = conn.cursor()

    # Clear previous summary
    if USE_POSTGRES:
        cur.execute("TRUNCATE invoice_items_temp;")
    else:
        cur.execute("DELETE FROM invoice_items_temp;")

    for name, qty, price, total in items:
        qty_f = clean_number(qty)
        price_f = clean_number(price)
        total_f = clean_number(total)

        db_execute(cur, """
            INSERT INTO invoice_items_temp (product_name, quantity, price, item_total)
            VALUES (%s, %s, %s, %s)
        """, (name, qty_f, price_f, total_f))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/purchase_summary")


# ---------------------------------------
# RUN APP
# ---------------------------------------
if __name__ == "__main__":
    app.run(debug=True)