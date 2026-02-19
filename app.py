from flask import Flask, render_template, request, redirect
import sqlite3
import psycopg2
import psycopg2.extras
from datetime import date
import random
import os

app = Flask(__name__)

# ---------------------------------------
# AUTO SWITCH: SQLite (local) vs PostgreSQL (Render)
# ---------------------------------------
IS_RENDER = os.environ.get("RENDER") == "true"

DATABASE_URL = os.environ.get("DATABASE_URL")  # Only set on Render


def get_db():
    if IS_RENDER:
        # Use PostgreSQL on Render
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        return conn
    else:
        # Use SQLite locally
        conn = sqlite3.connect("database.db")
        conn.row_factory = sqlite3.Row
        return conn


# ---------------------------------------
# INITIALIZE TABLES (Both DBs)
# ---------------------------------------
def init_db():
    conn = get_db()
    cur = conn.cursor()

    if IS_RENDER:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id SERIAL PRIMARY KEY,
                name TEXT,
                phone TEXT
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name TEXT,
                price REAL
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS bills (
                id SERIAL PRIMARY KEY,
                customer_id INTEGER REFERENCES customers(id),
                bill_date TEXT,
                total REAL
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS bill_items (
                id SERIAL PRIMARY KEY,
                bill_id INTEGER REFERENCES bills(id),
                product_id INTEGER REFERENCES products(id),
                price REAL,
                quantity REAL,
                item_total REAL
            );
        """)
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                phone TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                price REAL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS bills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                bill_date TEXT,
                total REAL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS bill_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bill_id INTEGER,
                product_id INTEGER,
                price REAL,
                quantity REAL,
                item_total REAL
            )
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

    # Count customers
    if IS_RENDER:
        cur.execute("SELECT COUNT(*) FROM customers;")
        existing = cur.fetchone()["count"]
    else:
        cur.execute("SELECT COUNT(*) FROM customers;")
        existing = cur.fetchone()[0]

    if existing > 0:
        cur.close()
        conn.close()
        return

    names = [
        "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun",
        "Reyansh", "Sai", "Krishna", "Ishaan",
        "Surya", "Ashok", "Ravi", "Rahul", "Vikram",
        "Ananya", "Diya", "Meera", "Priya", "Saanvi",
        "Lakshmi", "Kavya", "Neha", "Rohit", "Manoj",
        "Kiran", "Pooja", "Naveen", "Suresh", "Gopal"
    ]

    products = [
        "Rice", "Wheat", "Sugar", "Salt", "Oil",
        "Onion", "Potato", "Tomato", "Carrot", "Brinjal",
        "Milk", "Curd", "Butter", "Paneer", "Soap",
        "Shampoo", "Toothpaste", "Biscuit", "Tea Powder", "Coffee",
        "Dal", "Chilli Powder", "Turmeric", "Coriander", "Spinach"
    ]

    # Insert customers
    for i in range(1, 106):
        name = random.choice(names) + str(i)
        phone = "9" + str(random.randint(100000000, 999999999))

        if IS_RENDER:
            cur.execute("INSERT INTO customers (name, phone) VALUES (%s, %s)", (name, phone))
        else:
            cur.execute("INSERT INTO customers (name, phone) VALUES (?, ?)", (name, phone))

    # Insert products
    for p in products:
        price = random.randint(10, 200)

        if IS_RENDER:
            cur.execute("INSERT INTO products (name, price) VALUES (%s, %s)", (p, price))
        else:
            cur.execute("INSERT INTO products (name, price) VALUES (?, ?)", (p, price))

    conn.commit()
    cur.close()
    conn.close()


# Run setup
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

    if IS_RENDER:
        # PostgreSQL uses ILIKE
        base_query = """
            SELECT bills.id, bills.bill_date, bills.total,
                   customers.id AS customer_id,
                   customers.name AS customer_name
            FROM bills
            JOIN customers ON bills.customer_id = customers.id
        """
        if search:
            cur.execute(base_query + " WHERE customers.name ILIKE %s OR CAST(customers.id AS TEXT) ILIKE %s ORDER BY bills.id DESC",
                        (f"%{search}%", f"%{search}%"))
        else:
            cur.execute(base_query + " ORDER BY bills.id DESC")

        bills = cur.fetchall()
    else:
        # SQLite uses LIKE
        base_query = """
            SELECT bills.id, bills.bill_date, bills.total,
                   customers.id AS customer_id,
                   customers.name AS customer_name
            FROM bills
            JOIN customers ON bills.customer_id = customers.id
        """

        if search:
            cur.execute(base_query + " WHERE customers.name LIKE ? OR customers.id LIKE ? ORDER BY bills.id DESC",
                        (f"%{search}%", f"%{search}%"))
        else:
            cur.execute(base_query + " ORDER BY bills.id DESC")

        bills = cur.fetchall()

    # Bill items
    if IS_RENDER:
        cur.execute("""
            SELECT bill_items.bill_id,
                   products.name AS product_name,
                   bill_items.price,
                   bill_items.quantity,
                   bill_items.item_total
            FROM bill_items
            JOIN products ON bill_items.product_id = products.id
        """)
    else:
        cur.execute("""
            SELECT bill_items.bill_id,
                   products.name AS product_name,
                   bill_items.price,
                   bill_items.quantity,
                   bill_items.item_total
            FROM bill_items
            JOIN products ON bill_items.product_id = products.id
        """)

    bill_items = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("index.html", bills=bills, bill_items=bill_items, search=search)


# ---------------------------------------
# ADD BILL
# ---------------------------------------
@app.route("/add_bill", methods=["GET", "POST"])
def add_bill():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM customers ORDER BY id")
    customers = cur.fetchall()

    cur.execute("SELECT * FROM products ORDER BY id")
    products = cur.fetchall()

    if request.method == "POST":
        customer_id = request.form.get("customer")
        product_ids = request.form.getlist("product[]")
        prices = request.form.getlist("price[]")
        quantities = request.form.getlist("quantity[]")

        total = 0

        if IS_RENDER:
            cur.execute(
                "INSERT INTO bills (customer_id, bill_date, total) VALUES (%s, %s, %s) RETURNING id",
                (customer_id, date.today(), 0)
            )
            bill_id = cur.fetchone()["id"]
        else:
            cur.execute(
                "INSERT INTO bills (customer_id, bill_date, total) VALUES (?, ?, ?)",
                (customer_id, date.today(), 0)
            )
            bill_id = cur.lastrowid

        # Insert bill items
        for i in range(len(product_ids)):
            if prices[i] and quantities[i]:
                item_total = float(prices[i]) * float(quantities[i])
                total += item_total

                if IS_RENDER:
                    cur.execute("""
                        INSERT INTO bill_items (bill_id, product_id, price, quantity, item_total)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (bill_id, product_ids[i], prices[i], quantities[i], item_total))
                else:
                    cur.execute("""
                        INSERT INTO bill_items (bill_id, product_id, price, quantity, item_total)
                        VALUES (?, ?, ?, ?, ?)
                    """, (bill_id, product_ids[i], prices[i], quantities[i], item_total))

        # Update total
        if IS_RENDER:
            cur.execute("UPDATE bills SET total = %s WHERE id = %s", (total, bill_id))
        else:
            cur.execute("UPDATE bills SET total = ? WHERE id = ?", (total, bill_id))

        conn.commit()
        cur.close()
        conn.close()
        return redirect("/")

    cur.close()
    conn.close()
    return render_template("add_bill.html", customers=customers, products=products)


# ---------------------------------------
# RUN APP
# ---------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
