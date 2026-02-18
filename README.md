# 🧾 Flask Sales Management System

A simple personal sales management web application built using Flask and SQLite.

This application allows small business owners to:
- Store customer details
- Add multiple products per bill
- Automatically calculate totals
- View all bills
- Search bills by customer name or customer ID

## 🚀 Features

✔ Add new bill with multiple products  
✔ Auto calculation of item total and bill total  
✔ View all bills with customer details  
✔ Search by customer name or ID  
✔ Clean Bootstrap UI  
✔ SQLite database (lightweight and simple)  



## 🛠 Tech Stack

- Python
- Flask
- SQLite
- Bootstrap 5
- Gunicorn (for deployment)
- Render (for hosting)



## 📂 Project Structure

flask_sales/
│
├── app.py
├── requirements.txt
├── Procfile
├── .gitignore
├── database.db
│
└── templates/
├── layout.html
├── index.html
└── add_bill.html

yaml
Copy code



## ⚙️ Installation (Local Setup)

### 1️⃣ Clone Repository

git clone https://github.com/yourusername/flask-sales-management.git
cd flask-sales-management

shell
Copy code

### 2️⃣ Create Virtual Environment

python -m venv .venv
.venv\Scripts\activate

shell
Copy code

### 3️⃣ Install Dependencies

pip install -r requirements.txt

shell
Copy code

### 4️⃣ Run Application

python app.py

r
Copy code

Open in browser:

http://127.0.0.1:5000

yaml
Copy code



## 🌐 Deployment (Render)

1. Push project to GitHub  
2. Create new Web Service in Render  
3. Connect GitHub repository  
4. Set:

Build Command:
pip install -r requirements.txt

powershell
Copy code

Start Command:
gunicorn app:app

yaml
Copy code



## 📊 Database Structure

### Customers
- id
- name
- phone

### Products
- id
- name
- price

### Bills
- id
- customer_id
- bill_date
- total

### Bill Items
- id
- bill_id
- product_id
- price
- quantity
- item_total



## 🎯 Future Improvements

- Add Customer management page
- Add Product management page
- Add date filtering
- Add PDF invoice generation
- Add dashboard analytics
- Convert to PostgreSQL for production



## 👨‍💻 Author

Surya Nagi Reddy  
MSc Computer Science Student  
Aspiring Data Analyst / AI Engineer  


## 📌 License

This project is open-source and free to use for educational and personal purposes.
