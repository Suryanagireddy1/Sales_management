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
# UNIVERSAL QUERY EXECUTOR
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

    db_execute(cur, """
    CREATE TABLE IF NOT EXISTS customers(
        id SERIAL PRIMARY KEY,
        name TEXT
    )
    """)

    db_execute(cur, """
    CREATE TABLE IF NOT EXISTS products(
        id SERIAL PRIMARY KEY,
        name TEXT,
        price REAL
    )
    """)

    db_execute(cur, """
    CREATE TABLE IF NOT EXISTS bills(
        id SERIAL PRIMARY KEY,
        customer_id INTEGER,
        bill_date TEXT,
        total REAL
    )
    """)

    db_execute(cur, """
    CREATE TABLE IF NOT EXISTS bill_items(
        id SERIAL PRIMARY KEY,
        bill_id INTEGER,
        product_id INTEGER,
        price REAL,
        quantity REAL,
        item_total REAL
    )
    """)

    db_execute(cur, """
    CREATE TABLE IF NOT EXISTS invoice_items_temp(
        id SERIAL PRIMARY KEY,
        product_name TEXT,
        quantity REAL,
        price REAL,
        item_total REAL
    )
    """)

    conn.commit()
    cur.close()
    conn.close()


# ---------------------------------------
# INSERT PRODUCT LIST
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

    db_execute(cur, "DELETE FROM products")

    for item in items:
        db_execute(
            cur,
            "INSERT INTO products (name,price) VALUES (%s,%s)",
            (item,0)
        )

    conn.commit()
    cur.close()
    conn.close()


# ---------------------------------------
# RUN DB SETUP
# ---------------------------------------
with app.app_context():
    init_db()
    seed_products()


# ---------------------------------------
# HOME PAGE (FIXED)
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

    items = db_execute(cur,
    """
    SELECT bill_items.bill_id,
           products.name AS product_name,
           bill_items.price,
           bill_items.quantity,
           bill_items.item_total
    FROM bill_items
    JOIN products ON bill_items.product_id=products.id
    """,fetch=True)

    # GROUP ITEMS BY BILL
    bill_items = {}

    for item in items:
        bill_id = item["bill_id"]

        if bill_id not in bill_items:
            bill_items[bill_id] = []

        bill_items[bill_id].append(item)

    cur.close()
    conn.close()

    return render_template(
        "index.html",
        bills=bills,
        bill_items=bill_items
    )


# ---------------------------------------
# ADD BILL
# ---------------------------------------
@app.route("/add_bill",methods=["GET","POST"])
def add_bill():

    conn=get_db()
    cur=conn.cursor()

    customers=db_execute(cur,"SELECT * FROM customers ORDER BY id",fetch=True)
    products=db_execute(cur,"SELECT * FROM products ORDER BY name",fetch=True)

    if request.method=="POST":

        customer_id=request.form.get("customer")
        product_ids=request.form.getlist("product[]")
        prices=request.form.getlist("price[]")
        quantities=request.form.getlist("quantity[]")

        db_execute(cur,
        "INSERT INTO bills(customer_id,bill_date,total) VALUES(%s,%s,%s)",
        (customer_id,date.today(),0))

        if USE_POSTGRES:
            bill_id=db_execute(
                cur,
                "SELECT id FROM bills ORDER BY id DESC LIMIT 1",
                fetch=True
            )[0]["id"]
        else:
            bill_id=cur.lastrowid

        total=0

        for i in range(len(product_ids)):

            if prices[i] and quantities[i]:

                item_total=float(prices[i])*float(quantities[i])
                total+=item_total

                db_execute(cur,
                """INSERT INTO bill_items
                (bill_id,product_id,price,quantity,item_total)
                VALUES(%s,%s,%s,%s,%s)""",
                (bill_id,product_ids[i],prices[i],quantities[i],item_total))

        db_execute(cur,"UPDATE bills SET total=%s WHERE id=%s",(total,bill_id))

        conn.commit()
        cur.close()
        conn.close()

        return redirect("/")

    cur.close()
    conn.close()

    return render_template("add_bill.html",customers=customers,products=products)


# ---------------------------------------
# ADD CUSTOMER
# ---------------------------------------
@app.route("/add_customer",methods=["GET","POST"])
def add_customer():

    if request.method=="POST":

        cid=request.form.get("customer_id")
        name=request.form.get("name")

        conn=get_db()
        cur=conn.cursor()

        existing=db_execute(cur,
        "SELECT id FROM customers WHERE id=%s",(cid,),fetch=True)

        if existing:
            db_execute(cur,
            "UPDATE customers SET name=%s WHERE id=%s",(name,cid))
        else:
            db_execute(cur,
            "INSERT INTO customers(id,name) VALUES(%s,%s)",(cid,name))

        conn.commit()
        cur.close()
        conn.close()

        return redirect("/add_bill")

    return render_template("add_customer.html")


# ---------------------------------------
# PURCHASE SUMMARY
# ---------------------------------------
@app.route("/purchase_summary")
def purchase_summary():

    conn=get_db()
    cur=conn.cursor()

    summary=db_execute(cur,
    """
    SELECT product_name,
           SUM(quantity) AS total_quantity,
           AVG(price) AS avg_price,
           SUM(item_total) AS total_amount
    FROM invoice_items_temp
    GROUP BY product_name
    """,fetch=True)

    cur.close()
    conn.close()

    return render_template("purchase_summary.html",summary=summary)


# ---------------------------------------
# UPLOAD INVOICE
# ---------------------------------------
@app.route("/upload_invoice",methods=["GET","POST"])
def upload_invoice():

    if request.method=="GET":
        return render_template("upload_invoice.html")

    text_input=request.form.get("invoice_text","")
    file=request.files.get("invoice_file")

    uploaded_text=""

    if text_input:
        uploaded_text=text_input

    elif file and file.filename.endswith(".pdf"):

        os.makedirs("uploads",exist_ok=True)
        filepath="uploads/invoice.pdf"
        file.save(filepath)

        extracted=""

        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text=page.extract_text()
                if text:
                    extracted+=text+"\n"

        uploaded_text=extracted

    pattern=r"""
    ^\d+\s+
    ([A-Za-z0-9 /]+)\s+
    ([\d\.]+)\s+
    [A-Za-z]+\s+
    Rs\.?\s*([\d\.]+)\s+
    Rs\.?\s*([\d\.]+)
    """

    items=re.findall(pattern,uploaded_text,re.MULTILINE|re.VERBOSE)

    conn=get_db()
    cur=conn.cursor()

    cur.execute("DELETE FROM invoice_items_temp")

    for name,qty,price,total in items:

        qty=clean_number(qty)
        price=clean_number(price)
        total=clean_number(total)

        db_execute(cur,
        """INSERT INTO invoice_items_temp
        (product_name,quantity,price,item_total)
        VALUES(%s,%s,%s,%s)""",
        (name,qty,price,total))

    conn.commit()
    cur.close()
    conn.close()

    return redirect("/purchase_summary")


# ---------------------------------------
# RUN APP
# ---------------------------------------
if __name__=="__main__":
    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port)