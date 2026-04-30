import sqlite3
import os

DB_PATH = "buynow.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    # Products table
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        price REAL NOT NULL,
        stock INTEGER NOT NULL DEFAULT 0,
        category TEXT,
        image_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Customers table
    c.execute('''CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        address TEXT,
        city TEXT,
        pincode TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Orders table
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        total_amount REAL NOT NULL,
        status TEXT DEFAULT 'pending',
        payment_status TEXT DEFAULT 'unpaid',
        payment_method TEXT DEFAULT 'cod',
        courier_name TEXT,
        tracking_id TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id)
    )''')

    # Order items table
    c.execute('''CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        product_id INTEGER,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    )''')

    # Delivery tracking table
    c.execute('''CREATE TABLE IF NOT EXISTS delivery_tracking (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        status TEXT NOT NULL,
        location TEXT,
        description TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES orders(id)
    )''')

    # Courier services table
    c.execute('''CREATE TABLE IF NOT EXISTS couriers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        contact TEXT,
        api_key TEXT,
        active INTEGER DEFAULT 1
    )''')

    conn.commit()

    # Insert sample data if empty
    c.execute("SELECT COUNT(*) FROM products")
    if c.fetchone()[0] == 0:
        sample_products = [
            ("iPhone 15 Pro", "Apple iPhone 15 Pro 256GB Space Black", 134999, 25, "Electronics", "📱"),
            ("Samsung 4K TV", "Samsung 55inch QLED 4K Smart TV", 89999, 12, "Electronics", "📺"),
            ("Nike Air Max", "Nike Air Max 270 Running Shoes", 12999, 50, "Footwear", "👟"),
            ("Levis Jeans", "Levis 501 Original Fit Dark Blue", 4999, 80, "Clothing", "👖"),
            ("Sony Headphones", "Sony WH-1000XM5 Noise Cancelling", 34999, 18, "Electronics", "🎧"),
            ("MacBook Air M3", "Apple MacBook Air 13inch M3 Chip 16GB", 124999, 8, "Computers", "💻"),
            ("Adidas T-Shirt", "Adidas Originals Cotton T-Shirt", 1999, 120, "Clothing", "👕"),
            ("Coffee Maker", "Nespresso Vertuo Pop Coffee Machine", 8999, 30, "Home", "☕"),
            ("Gaming Chair", "DXRacer Formula Series Gaming Chair", 24999, 15, "Furniture", "🪑"),
            ("Smart Watch", "Apple Watch Series 9 GPS 45mm", 44999, 22, "Electronics", "⌚"),
        ]
        c.executemany("INSERT INTO products (name, description, price, stock, category, image_url) VALUES (?,?,?,?,?,?)", sample_products)

        # Sample couriers
        sample_couriers = [
            ("BlueDart", "1800-233-1234", "BD_API_001"),
            ("Delhivery", "1800-123-8000", "DL_API_002"),
            ("DTDC", "1800-209-3455", "DTDC_API_003"),
            ("Ekart Logistics", "1800-419-3278", "EK_API_004"),
        ]
        c.executemany("INSERT INTO couriers (name, contact, api_key) VALUES (?,?,?)", sample_couriers)

        conn.commit()

    conn.close()
    print("✅ Database initialized successfully!")

if __name__ == "__main__":
    init_db()