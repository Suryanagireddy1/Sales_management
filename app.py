from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import date
import random
import os

app = Flask(__name__)

# -----------------------------
# DATABASE CONNECTION
# -----------------------------
def get_db():
    conn = sqlite3.connect("database.db", timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


# -----------------------------
# INITIALIZE DATABASE
# -----------------------------
def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price REAL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            bill_date TEXT,
            total REAL
        )
    """)

    conn.execute("""
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
    conn.close()


# -----------------------------
# SEED TEST DATA
# -----------------------------
def seed_data():
    conn = get_db()

    existing = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    if existing > 0:
        conn.close()
        return

    indian_names = [
        "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun",
        "Reyansh", "Sai", "Krishna", "Ishaan",
        "Surya", "Ashok", "Ravi", "Rahul", "Vikram",
        "Ananya", "Diya", "Meera", "Priya", "Saanvi",
        "Lakshmi", "Kavya", "Neha", "Rohit", "Manoj",
        "Kiran", "Pooja", "Naveen", "Suresh", "Gopal"
    ]

    product_list = [
        "Rice", "Wheat", "Sugar", "Salt", "Oil",
        "Onion", "Potato", "Tomato", "Carrot", "Brinjal",
        "Milk", "Curd", "Butter", "Paneer", "Soap",
        "Shampoo", "Toothpaste", "Biscuit", "Tea Powder", "Coffee",
        "Dal", "Chilli Powder", "Turmeric", "Coriander", "Spinach"
    ]

    # Insert 106 customers
    for i in range(1,106):
        name = random.choice(indian_names) + str(i)
        phone = "9" + str(random.randint(100000000, 999999999))
        conn.execute(
            "INSERT INTO customers (name, phone) VALUES (?, ?)",
            (name, phone)
        )

    # Insert products
    for product in product_list:
        price = random.randint(10, 200)
        conn.execute(
            "INSERT INTO products (name, price) VALUES (?, ?)",
            (product, price)
        )

    conn.commit()
    conn.close()


# -----------------------------
# HOME PAGE
# -----------------------------
@app.route("/")
def index():
    conn = get_db()

    search = request.args.get("search")

    base_query = """
        SELECT bills.id,
               bills.bill_date,
               bills.total,
               customers.id AS customer_id,
               customers.name AS customer_name
        FROM bills
        JOIN customers ON bills.customer_id = customers.id
    """

    if search:
        base_query += """
            WHERE customers.name LIKE ?
            OR customers.id LIKE ?
        """
        bills = conn.execute(
            base_query + " ORDER BY bills.id DESC",
            (f"%{search}%", f"%{search}%")
        ).fetchall()
    else:
        bills = conn.execute(
            base_query + " ORDER BY bills.id DESC"
        ).fetchall()

    bill_items = conn.execute("""
        SELECT bill_items.bill_id,
               products.name AS product_name,
               bill_items.price,
               bill_items.quantity,
               bill_items.item_total
        FROM bill_items
        JOIN products ON bill_items.product_id = products.id
    """).fetchall()

    conn.close()

    return render_template(
        "index.html",
        bills=bills,
        bill_items=bill_items,
        search=search
    )


# -----------------------------
# ADD BILL
# -----------------------------
@app.route("/add_bill", methods=["GET", "POST"])
def add_bill():
    conn = get_db()

    customers = conn.execute("SELECT * FROM customers").fetchall()
    products = conn.execute("SELECT * FROM products").fetchall()

    if request.method == "POST":
        try:
            customer_id = request.form.get("customer")
            product_ids = request.form.getlist("product[]")
            prices = request.form.getlist("price[]")
            quantities = request.form.getlist("quantity[]")

            if not customer_id:
                return "Customer not selected"

            total = 0

            conn.execute(
                "INSERT INTO bills (customer_id, bill_date, total) VALUES (?, ?, ?)",
                (customer_id, date.today(), 0)
            )

            bill_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            for i in range(len(product_ids)):
                if prices[i] and quantities[i]:
                    item_total = float(prices[i]) * float(quantities[i])
                    total += item_total

                    conn.execute("""
                        INSERT INTO bill_items (bill_id, product_id, price, quantity, item_total)
                        VALUES (?, ?, ?, ?, ?)
                    """, (bill_id, product_ids[i], prices[i], quantities[i], item_total))

            conn.execute(
                "UPDATE bills SET total=? WHERE id=?",
                (total, bill_id)
            )

            conn.commit()

        finally:
            conn.close()

        return redirect("/")

    conn.close()
    return render_template("add_bill.html", customers=customers, products=products)


# -----------------------------
# RUN APP
# -----------------------------
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
