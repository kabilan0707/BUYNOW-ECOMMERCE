from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from database import get_db, init_db
import json
import random
import string
from datetime import datetime

app = Flask(__name__)
app.secret_key = "buynow_secret_key_2024"


# ─────────────────────────────────────────────
#  HELPER FUNCTIONS
# ─────────────────────────────────────────────

def generate_tracking_id():
    return "BN" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))


def add_tracking_event(order_id, status, location, description):
    db = get_db()
    db.execute(
        "INSERT INTO delivery_tracking (order_id, status, location, description) VALUES (?,?,?,?)",
        (order_id, status, location, description)
    )
    db.commit()
    db.close()


# ─────────────────────────────────────────────
#  USER ROUTES
# ─────────────────────────────────────────────

@app.route("/")
def index():
    db = get_db()
    products = db.execute("SELECT * FROM products ORDER BY id").fetchall()
    categories = db.execute("SELECT DISTINCT category FROM products").fetchall()
    db.close()
    return render_template("index.html", products=products, categories=categories)


@app.route("/api/products")
def api_products():
    db = get_db()
    category = request.args.get("category", "")
    search = request.args.get("search", "")

    query = "SELECT * FROM products WHERE 1=1"
    params = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if search:
        query += " AND (name LIKE ? OR description LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    products = db.execute(query, params).fetchall()
    db.close()
    return jsonify([dict(p) for p in products])


@app.route("/api/stock/<int:product_id>")
def check_stock(product_id):
    db = get_db()
    product = db.execute("SELECT id, name, stock FROM products WHERE id = ?", (product_id,)).fetchone()
    db.close()
    if product:
        return jsonify({"id": product["id"], "name": product["name"], "stock": product["stock"],
                        "available": product["stock"] > 0})
    return jsonify({"error": "Product not found"}), 404


@app.route("/api/checkout", methods=["POST"])
def checkout():
    data = request.json
    cart = data.get("cart", [])
    customer = data.get("customer", {})
    payment_method = data.get("payment_method", "cod")

    if not cart or not customer:
        return jsonify({"error": "Cart and customer details required"}), 400

    db = get_db()

    try:
        # Check/Create customer
        existing = db.execute("SELECT id FROM customers WHERE email = ?", (customer["email"],)).fetchone()
        if existing:
            customer_id = existing["id"]
            db.execute(
                "UPDATE customers SET name=?, phone=?, address=?, city=?, pincode=? WHERE id=?",
                (customer["name"], customer["phone"], customer["address"], customer["city"], customer["pincode"],
                 customer_id)
            )
        else:
            cursor = db.execute(
                "INSERT INTO customers (name, email, phone, address, city, pincode) VALUES (?,?,?,?,?,?)",
                (customer["name"], customer["email"], customer["phone"], customer["address"], customer["city"],
                 customer["pincode"])
            )
            customer_id = cursor.lastrowid

        # Validate stock and calculate total
        total = 0
        items_to_process = []
        for item in cart:
            product = db.execute("SELECT * FROM products WHERE id = ?", (item["id"],)).fetchone()
            if not product:
                return jsonify({"error": f"Product {item['id']} not found"}), 404
            if product["stock"] < item["qty"]:
                return jsonify(
                    {"error": f"Insufficient stock for {product['name']}. Only {product['stock']} left."}), 400
            total += product["price"] * item["qty"]
            items_to_process.append({"product": product, "qty": item["qty"]})

        # Create order
        tracking_id = generate_tracking_id()
        order_cursor = db.execute(
            "INSERT INTO orders (customer_id, total_amount, status, payment_status, payment_method, tracking_id) VALUES (?,?,?,?,?,?)",
            (customer_id, total, "confirmed", "unpaid" if payment_method == "cod" else "paid", payment_method,
             tracking_id)
        )
        order_id = order_cursor.lastrowid

        # Insert order items & reduce stock
        for item in items_to_process:
            db.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?,?,?,?)",
                (order_id, item["product"]["id"], item["qty"], item["product"]["price"])
            )
            db.execute(
                "UPDATE products SET stock = stock - ? WHERE id = ?",
                (item["qty"], item["product"]["id"])
            )

        # Initial tracking event
        db.execute(
            "INSERT INTO delivery_tracking (order_id, status, location, description) VALUES (?,?,?,?)",
            (order_id, "Order Placed", customer["city"], f"Order #{order_id} confirmed. Tracking ID: {tracking_id}")
        )

        db.commit()
        db.close()

        return jsonify({
            "success": True,
            "order_id": order_id,
            "tracking_id": tracking_id,
            "total": total,
            "message": "Order placed successfully!"
        })

    except Exception as e:
        db.close()
        return jsonify({"error": str(e)}), 500


@app.route("/tracking/<tracking_id>")
def tracking(tracking_id):
    db = get_db()
    order = db.execute(
        """SELECT o.*, c.name as customer_name, c.city, c.address, c.phone
           FROM orders o
                    JOIN customers c ON o.customer_id = c.id
           WHERE o.tracking_id = ?""", (tracking_id,)
    ).fetchone()

    if not order:
        db.close()
        return render_template("tracking.html", error="Order not found", tracking_id=tracking_id)

    events = db.execute(
        "SELECT * FROM delivery_tracking WHERE order_id = ? ORDER BY timestamp ASC",
        (order["id"],)
    ).fetchall()

    items = db.execute(
        """SELECT oi.*, p.name as product_name, p.image_url
           FROM order_items oi
                    JOIN products p ON oi.product_id = p.id
           WHERE oi.order_id = ?""", (order["id"],)
    ).fetchall()

    db.close()
    return render_template("tracking.html", order=dict(order), events=[dict(e) for e in events],
                           items=[dict(i) for i in items], tracking_id=tracking_id)


@app.route("/api/tracking/<tracking_id>")
def api_tracking(tracking_id):
    db = get_db()
    order = db.execute("SELECT * FROM orders WHERE tracking_id = ?", (tracking_id,)).fetchone()
    if not order:
        db.close()
        return jsonify({"error": "Not found"}), 404
    events = db.execute(
        "SELECT * FROM delivery_tracking WHERE order_id = ? ORDER BY timestamp DESC",
        (order["id"],)
    ).fetchall()
    db.close()
    return jsonify({"order": dict(order), "events": [dict(e) for e in events]})


# ─────────────────────────────────────────────
#  ADMIN DASHBOARD ROUTES
# ─────────────────────────────────────────────

@app.route("/dashboard")
def dashboard():
    db = get_db()

    stats = {
        "total_orders": db.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        "pending_orders": db.execute("SELECT COUNT(*) FROM orders WHERE status='confirmed'").fetchone()[0],
        "shipped_orders": db.execute("SELECT COUNT(*) FROM orders WHERE status='shipped'").fetchone()[0],
        "delivered_orders": db.execute("SELECT COUNT(*) FROM orders WHERE status='delivered'").fetchone()[0],
        "total_revenue":
            db.execute("SELECT COALESCE(SUM(total_amount),0) FROM orders WHERE payment_status='paid'").fetchone()[0],
        "total_products": db.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "low_stock": db.execute("SELECT COUNT(*) FROM products WHERE stock < 10").fetchone()[0],
        "total_customers": db.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
    }

    recent_orders = db.execute(
        """SELECT o.*, c.name as customer_name, c.city
           FROM orders o
                    JOIN customers c ON o.customer_id = c.id
           ORDER BY o.created_at DESC LIMIT 10"""
    ).fetchall()

    products = db.execute("SELECT * FROM products ORDER BY stock ASC").fetchall()
    couriers = db.execute("SELECT * FROM couriers WHERE active=1").fetchall()

    db.close()
    return render_template("dashboard.html", stats=stats, recent_orders=recent_orders, products=products,
                           couriers=couriers)


@app.route("/api/orders")
def api_orders():
    db = get_db()
    status = request.args.get("status", "")
    query = """SELECT o.*, c.name as customer_name, c.city, c.phone
               FROM orders o \
                        JOIN customers c ON o.customer_id = c.id"""
    params = []
    if status:
        query += " WHERE o.status = ?"
        params.append(status)
    query += " ORDER BY o.created_at DESC"
    orders = db.execute(query, params).fetchall()
    db.close()
    return jsonify([dict(o) for o in orders])


@app.route("/api/order/<int:order_id>")
def api_order_detail(order_id):
    db = get_db()
    order = db.execute(
        """SELECT o.*, c.name as customer_name, c.email, c.phone, c.address, c.city, c.pincode
           FROM orders o
                    JOIN customers c ON o.customer_id = c.id
           WHERE o.id = ?""",
        (order_id,)
    ).fetchone()
    if not order:
        return jsonify({"error": "Not found"}), 404
    items = db.execute(
        """SELECT oi.*, p.name, p.image_url
           FROM order_items oi
                    JOIN products p ON oi.product_id = p.id
           WHERE oi.order_id = ?""",
        (order_id,)
    ).fetchall()
    events = db.execute(
        "SELECT * FROM delivery_tracking WHERE order_id = ? ORDER BY timestamp ASC",
        (order_id,)
    ).fetchall()
    db.close()
    return jsonify({
        "order": dict(order),
        "items": [dict(i) for i in items],
        "events": [dict(e) for e in events]
    })


@app.route("/api/order/<int:order_id>/update", methods=["POST"])
def update_order(order_id):
    data = request.json
    new_status = data.get("status")
    courier_name = data.get("courier_name")
    payment_status = data.get("payment_status")
    location = data.get("location", "Warehouse")
    description = data.get("description", "")

    db = get_db()

    order = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        db.close()
        return jsonify({"error": "Order not found"}), 404

    updates = ["updated_at = CURRENT_TIMESTAMP"]
    params = []

    if new_status:
        updates.append("status = ?")
        params.append(new_status)
    if courier_name:
        updates.append("courier_name = ?")
        params.append(courier_name)
    if payment_status:
        updates.append("payment_status = ?")
        params.append(payment_status)

    params.append(order_id)
    db.execute(f"UPDATE orders SET {', '.join(updates)} WHERE id = ?", params)

    # Auto tracking event descriptions
    status_messages = {
        "confirmed": "Order confirmed and processing started",
        "packed": "Items packed and ready for dispatch",
        "shipped": f"Handed over to {courier_name or order['courier_name'] or 'courier'} for delivery",
        "out_for_delivery": "Out for delivery - expect delivery today",
        "delivered": "Successfully delivered to customer",
        "cancelled": "Order has been cancelled"
    }

    if new_status:
        event_desc = description or status_messages.get(new_status, f"Status updated to {new_status}")
        db.execute(
            "INSERT INTO delivery_tracking (order_id, status, location, description) VALUES (?,?,?,?)",
            (order_id, new_status.replace("_", " ").title(), location, event_desc)
        )

    db.commit()
    db.close()
    return jsonify({"success": True, "message": "Order updated successfully"})


@app.route("/api/product/add", methods=["POST"])
def add_product():
    data = request.json
    db = get_db()
    db.execute(
        "INSERT INTO products (name, description, price, stock, category, image_url) VALUES (?,?,?,?,?,?)",
        (data["name"], data.get("description", ""), data["price"], data["stock"], data.get("category", "General"),
         data.get("image_url", "📦"))
    )
    db.commit()
    db.close()
    return jsonify({"success": True})


@app.route("/api/product/<int:product_id>/update", methods=["POST"])
def update_product(product_id):
    data = request.json
    db = get_db()
    db.execute(
        "UPDATE products SET name=?, price=?, stock=?, category=?, description=? WHERE id=?",
        (data["name"], data["price"], data["stock"], data["category"], data.get("description", ""), product_id)
    )
    db.commit()
    db.close()
    return jsonify({"success": True})


@app.route("/api/product/<int:product_id>/delete", methods=["DELETE"])
def delete_product(product_id):
    db = get_db()
    db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    db.commit()
    db.close()
    return jsonify({"success": True})


@app.route("/api/payment/<int:order_id>/update", methods=["POST"])
def update_payment(order_id):
    data = request.json
    status = data.get("payment_status", "paid")
    db = get_db()
    db.execute("UPDATE orders SET payment_status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, order_id))
    if status == "paid":
        db.execute(
            "INSERT INTO delivery_tracking (order_id, status, location, description) VALUES (?,?,?,?)",
            (order_id, "Payment Confirmed", "Online", f"Payment received. Status: {status.upper()}")
        )
    db.commit()
    db.close()
    return jsonify({"success": True})


@app.route("/api/dashboard/stats")
def dashboard_stats():
    db = get_db()
    stats = {
        "total_orders": db.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        "pending": db.execute("SELECT COUNT(*) FROM orders WHERE status='confirmed'").fetchone()[0],
        "shipped": db.execute("SELECT COUNT(*) FROM orders WHERE status='shipped'").fetchone()[0],
        "delivered": db.execute("SELECT COUNT(*) FROM orders WHERE status='delivered'").fetchone()[0],
        "revenue":
            db.execute("SELECT COALESCE(SUM(total_amount),0) FROM orders WHERE payment_status='paid'").fetchone()[0],
        "low_stock_products": [dict(p) for p in db.execute(
            "SELECT name, stock FROM products WHERE stock < 10 ORDER BY stock").fetchall()]
    }
    db.close()
    return jsonify(stats)


if __name__ == "__main__":
    init_db()
    print("🚀 BUYNOW Server starting at http://localhost:5000")
    print("📦 Store: http://localhost:5000")
    print("📊 Dashboard: http://localhost:5000/dashboard")
    app.run(debug=True, port=5000)