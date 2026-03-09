import pdfplumber
import re
from flask import Flask, render_template, request, redirect
import sqlite3
import psycopg2
import psycopg2.extras
from datetime import date
import os

app = Flask(__name__)

# ---------------------------------------
# DATABASE SWITCH
# ---------------------------------------
USE_POSTGRES = bool(os.environ.get("DATABASE_URL"))
DATABASE_URL = os.environ.get("DATABASE_URL")


# ---------------------------------------
# DATABASE CONNECTION
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
# QUERY EXECUTOR
# ---------------------------------------
def db_execute(cur, query, params=None, fetch=False):

    if not USE_POSTGRES:
        query = query.replace("%s", "?")

    if params:
        cur.execute(query, params)
    else:
        cur.execute(query)

    if fetch:
        return cur.fetchall()

    return None


# ---------------------------------------
# CLEAN NUMBER
# ---------------------------------------
def clean_number(value):
    if not value:
        return 0.0

    value = value.replace(",", "").replace("Rs", "").replace("₹", "")
    value = value.replace(":", "").replace(" ", "").strip()

    try:
        return float(value)
    except:
        return 0.0


# ---------------------------------------
# CREATE TABLES
# ---------------------------------------
def init_db():

    conn = get_db()
    cur = conn.cursor()

    db_execute(cur,
    """
    CREATE TABLE IF NOT EXISTS customers(
        id SERIAL PRIMARY KEY,
        name TEXT
    )
    """)

    db_execute(cur,
    """
    CREATE TABLE IF NOT EXISTS products(
        id SERIAL PRIMARY KEY,
        name TEXT,
        price REAL
    )
    """)

    db_execute(cur,
    """
    CREATE TABLE IF NOT EXISTS bills(
        id SERIAL PRIMARY KEY,
        customer_id INTEGER,
        bill_date TEXT,
        total REAL
    )
    """)

    db_execute(cur,
    """
    CREATE TABLE IF NOT EXISTS bill_items(
        id SERIAL PRIMARY KEY,
        bill_id INTEGER,
        product_id INTEGER,
        price REAL,
        quantity REAL,
        item_total REAL
    )
    """)

    db_execute(cur,
    """
    CREATE TABLE IF NOT EXISTS invoice_items_temp(
        id SERIAL PRIMARY KEY,
        product_name TEXT,
        quantity REAL,
        price REAL,
        item_total REAL
    )
    """)

    conn.commit()
    conn.close()


# ---------------------------------------
# SEED PRODUCTS
# ---------------------------------------
def seed_products():

    items = [
        "Amla","Amaranth","Barbati","Beetroot","Bitter Gourd","Black Brinjal",
        "Black Eggplant","Bottle Gourd","Broad Beans Ramabhadrapuram","Cabbage",
        "Carrot","Cauliflower","Chana dal","Chrysanthemum","Coconut","Colocasia",
        "Coriander","Cucumber","Curry leaves","Dry Red Chilli","Drumsticks",
        "Fenugreek Leaves","French Beans","Garlic","Ginger","Gongura",
        "Green Chilli","Green Peas","Guava","Ivy gourd","Lady Finger / Bhindi",
        "Lemon","Malabar Spinach","Mango Ginger","Marigold Garland",
        "Marigold Flowers","Muskmelon","Mushrooms","Onion","Papaya fruit",
        "Potato","Pomegranate","Raw Banana","Red Rose","Ridge Gourd",
        "Rose Flowers","Sapota","Spinach","Spinach Dock","Spring Onion",
        "Sweet Potato","Tamarind (seed less)","Tomato","White Brinjal",
        "White Chrysanthemum","White Radish","Bachali Kura"
    ]

    conn = get_db()
    cur = conn.cursor()

    db_execute(cur,"DELETE FROM products")

    for item in items:
        db_execute(cur,
        "INSERT INTO products(name,price) VALUES(%s,%s)",
        (item,0))

    conn.commit()
    conn.close()


with app.app_context():
    init_db()
    seed_products()


# ---------------------------------------
# HOME PAGE
# ---------------------------------------
@app.route("/")
def index():

    conn = get_db()
    cur = conn.cursor()

    bills = db_execute(cur,
    """
    SELECT bills.id,bills.bill_date,bills.total,
           customers.name AS customer_name,
           customers.id AS customer_id
    FROM bills
    JOIN customers ON bills.customer_id=customers.id
    ORDER BY bills.id DESC
    """,fetch=True)

    # attach items to each bill
    for bill in bills:

        items = db_execute(cur,
        """
        SELECT products.name AS product_name,
               bill_items.price,
               bill_items.quantity,
               bill_items.item_total
        FROM bill_items
        JOIN products ON bill_items.product_id=products.id
        WHERE bill_items.bill_id=%s
        """,
        (bill["id"],),
        fetch=True)

        bill["items"] = items

    conn.close()

    return render_template("index.html", bills=bills)


# ---------------------------------------
# ADD BILL
# ---------------------------------------
@app.route("/add_bill",methods=["GET","POST"])
def add_bill():

    conn = get_db()
    cur = conn.cursor()

    customers = db_execute(cur,"SELECT * FROM customers",fetch=True)
    products = db_execute(cur,"SELECT * FROM products ORDER BY name",fetch=True)

    if request.method == "POST":

        customer_id = request.form.get("customer")
        product_ids = request.form.getlist("product[]")
        prices = request.form.getlist("price[]")
        quantities = request.form.getlist("quantity[]")

        if USE_POSTGRES:

            cur.execute(
                "INSERT INTO bills(customer_id,bill_date,total) VALUES(%s,%s,%s) RETURNING id",
                (customer_id,date.today(),0)
            )

            bill_id = cur.fetchone()["id"]

        else:

            db_execute(cur,
            "INSERT INTO bills(customer_id,bill_date,total) VALUES(%s,%s,%s)",
            (customer_id,date.today(),0))

            bill_id = cur.lastrowid

        total = 0

        for i in range(len(product_ids)):

            if prices[i] and quantities[i]:

                item_total = float(prices[i]) * float(quantities[i])
                total += item_total

                db_execute(cur,
                """INSERT INTO bill_items
                (bill_id,product_id,price,quantity,item_total)
                VALUES(%s,%s,%s,%s,%s)""",
                (bill_id,product_ids[i],prices[i],quantities[i],item_total))

        db_execute(cur,
        "UPDATE bills SET total=%s WHERE id=%s",
        (total,bill_id))

        conn.commit()
        conn.close()

        return redirect("/")

    conn.close()

    return render_template("add_bill.html",
        customers=customers,
        products=products
    )