# Admin Dashboard — Required Backend Endpoints

Every page in the dashboard and what it needs from the backend.
Endpoints marked ✅ already exist in your Postman collection.
Endpoints marked ❌ are **missing and must be added** to Django.

---

## 1. Authentication — `/api/users/`

### ✅ Login (already exists)
```
POST /api/users/login/
Body: { "email": "admin@example.com", "password": "..." }
Response: { "access": "...", "refresh": "..." }
```

### ✅ Refresh Token (already exists)
```
POST /api/users/token/refresh/
Body: { "refresh": "..." }
Response: { "access": "..." }
```

### ✅ Forgot Password (already exists)
```
POST /api/users/forgot-password/
Body: { "email": "..." }
Response: { "message": "OTP sent" }
```

### ✅ Verify OTP (already exists)
```
POST /api/users/verify-otp/
Body: { "email": "...", "code": "12345" }
Response: { "message": "OTP verified" }
```

### ✅ Reset Password (already exists)
```
POST /api/users/reset-password/
Body: { "email": "...", "new_password": "...", "confirm_password": "..." }
Response: { "message": "Password updated" }
```

### ❌ Change Password (logged-in admin) — MISSING
Used by: **Settings → Security page**
```
POST /api/users/change-password/
Headers: Authorization: Bearer <token>
Body: { "current_password": "...", "new_password": "...", "confirm_password": "..." }
Response: { "message": "Password changed successfully" }
```

---

## 2. Admin Profile — `/api/admin/`

### ❌ Get Admin Profile — MISSING
Used by: **Settings → Profile page** (to pre-fill name, email, phone fields)
```
GET /api/admin/profile/
Headers: Authorization: Bearer <token>
Response: {
  "id": 1,
  "full_name": "John Smith",
  "email": "admin@example.com",
  "phone": "+1 (555) 000-0000",
  "avatar": "http://localhost:8000/media/avatars/admin.jpg"  // null if not set
}
```

### ❌ Update Admin Profile — MISSING
Used by: **Settings → Profile page** (Save Changes button)
```
PATCH /api/admin/profile/
Headers: Authorization: Bearer <token>, Content-Type: multipart/form-data
Body (form-data):
  full_name: "John Smith"
  phone: "+1 (555) 000-0000"
  avatar: <file>  // optional image upload
Response: { same shape as GET above }
```

---

## 3. Dashboard Overview Stats — `/api/admin/`

### ❌ Dashboard Stats — MISSING
Used by: **Dashboard home page** (the 4 stat cards: Total Orders, Total Products, Total Customers, Total Revenue)
```
GET /api/admin/dashboard/stats/
Headers: Authorization: Bearer <token>
Response: {
  "total_orders": 125,
  "total_products": 34,
  "total_customers": 642,
  "total_revenue": 82120.00
}
```

### ❌ Orders Chart Data — MISSING
Used by: **Dashboard home page** (the weekly orders bar/line chart)
```
GET /api/admin/dashboard/chart/
Headers: Authorization: Bearer <token>
Query params: ?period=week  (optional, default=week)
Response: [
  { "date": "Mon", "orders": 21 },
  { "date": "Tue", "orders": 28 },
  { "date": "Wed", "orders": 17 },
  { "date": "Thu", "orders": 24 },
  { "date": "Fri", "orders": 32 },
  { "date": "Sat", "orders": 14 },
  { "date": "Sun", "orders": 26 }
]
```

### ❌ Recent Transactions — MISSING
Used by: **Dashboard home page** (the recent transactions side table)
```
GET /api/admin/dashboard/transactions/
Headers: Authorization: Bearer <token>
Query params: ?limit=5
Response: [
  {
    "id": "TX-001",
    "user": "Liam Johnson",
    "amount": 350.00,
    "status": "Completed",  // "Completed" | "Pending" | "Failed"
    "date": "2023-10-01T12:00:00Z"
  },
  ...
]
```

---

## 4. Orders — `/api/admin/orders/`

### ❌ List All Orders (Admin) — MISSING
Used by: **Orders page** (the orders table)

> The existing GET /api/orders/ only returns the logged-in user's own orders. Admin needs ALL orders from ALL customers.

```
GET /api/admin/orders/
Headers: Authorization: Bearer <token>
Query params: ?page=1&page_size=10&status=Pending  (all optional)
Response: {
  "count": 125,
  "next": "http://localhost:8000/api/admin/orders/?page=2",
  "previous": null,
  "results": [
    {
      "id": "ORD-2026-001234",
      "customer": "Alex Johnson",
      "date": "2023-10-24",
      "total": 130.00,
      "status": "Pending",   // "Pending" | "Shipped" | "Delivered" | "Cancelled"
      "tracking_number": "USPS9405...",
      "items": [
        {
          "name": "ADHD T-Shirt",
          "image": "http://...",
          "size": "M",
          "color": "Blue",
          "qty": 1,
          "price": 65.00
        }
      ]
    }
  ]
}
```

### ❌ Update Order Status (Admin) — MISSING
Used by: **Orders page** → Mark Shipped / Mark Delivered / Cancel Order actions
```
PATCH /api/admin/orders/{order_number}/
Headers: Authorization: Bearer <token>
Body: { "status": "Shipped" }  // "Shipped" | "Delivered" | "Cancelled"
Response: { same shape as single order above }
```

---

## 5. Products — `/api/admin/products/`

### ✅ List Products (already exists — shop endpoint is fine for reading)

### ❌ Create Product — MISSING
Used by: **Products page** → Add Product modal
```
POST /api/admin/products/
Headers: Authorization: Bearer <token>, Content-Type: multipart/form-data
Body (form-data):
  name: "ADHD T-Shirt"
  category_slug: "t-shirts"
  price: 65.00
  stock: 42
  sizes: "S,M,L,XL"
  image: <file>
Response: {
  "id": 16,
  "name": "ADHD T-Shirt",
  "category": "T-Shirt",
  "price": "65.00",
  "inventory": 42,
  "image": "http://...",
  "variants": [
    { "size": "S", "stock": 10 },
    { "size": "M", "stock": 15 },
    { "size": "L", "stock": 12 },
    { "size": "XL", "stock": 5 }
  ]
}
```

### ❌ Update Product — MISSING
Used by: **Products page** → Edit Product modal
```
PATCH /api/admin/products/{id}/
Headers: Authorization: Bearer <token>, Content-Type: multipart/form-data
Body (form-data, all optional):
  price: 70.00
  variants: [{"size":"S","stock":5},{"size":"M","stock":0}]
  image: <file>
Response: { same shape as Create above }
```

### ❌ Delete Product — MISSING
Used by: **Products page** → Delete Product confirmation modal
```
DELETE /api/admin/products/{id}/
Headers: Authorization: Bearer <token>
Response: 204 No Content
```

---

## 6. Customers — `/api/admin/customers/`

### ❌ List All Customers (Admin) — MISSING
Used by: **Customers page** (the customers table)

> There is no endpoint to list all platform users. GET /api/profiles/me/ only returns the logged-in user's own profile.

```
GET /api/admin/customers/
Headers: Authorization: Bearer <token>
Query params: ?page=1&page_size=10
Response: {
  "count": 642,
  "next": "...",
  "previous": null,
  "results": [
    {
      "id": 1,
      "name": "Alex Johnson",
      "email": "alex@example.com",
      "phone": "+1 (555) 101-0001",
      "status": "Active",       // "Active" | "Inactive"
      "joined": "2022-03-14",
      "total_orders": 4,
      "total_spent": 450.50,
      "last_order_date": "2023-10-24",
      "order_history": [
        {
          "id": "ORD-2026-001234",
          "date": "2023-10-24",
          "total": 130.00,
          "status": "Pending"
        }
      ]
    }
  ]
}
```

### ❌ Update Customer (Admin) — MISSING
Used by: **Customers page** → Edit Customer modal
```
PATCH /api/admin/customers/{id}/
Headers: Authorization: Bearer <token>
Body: { "name": "Alex Rivera", "email": "...", "phone": "..." }
Response: { same shape as single customer above }
```

### ❌ Delete Customer (Admin) — MISSING
Used by: **Customers page** → Delete Customer confirmation modal
```
DELETE /api/admin/customers/{id}/
Headers: Authorization: Bearer <token>
Response: 204 No Content
```

---

## Summary Table

| # | Method | Endpoint | Used By |
|---|--------|----------|---------|
| 1 | `POST` | `/api/users/change-password/` | Settings → Security |
| 2 | `GET` | `/api/admin/profile/` | Settings → Profile |
| 3 | `PATCH` | `/api/admin/profile/` | Settings → Profile |
| 4 | `GET` | `/api/admin/dashboard/stats/` | Dashboard Overview |
| 5 | `GET` | `/api/admin/dashboard/chart/` | Dashboard Overview |
| 6 | `GET` | `/api/admin/dashboard/transactions/` | Dashboard Overview |
| 7 | `GET` | `/api/admin/orders/` | Orders Page |
| 8 | `PATCH` | `/api/admin/orders/{order_number}/` | Orders Page |
| 9 | `POST` | `/api/admin/products/` | Products Page |
| 10 | `PATCH` | `/api/admin/products/{id}/` | Products Page |
| 11 | `DELETE` | `/api/admin/products/{id}/` | Products Page |
| 12 | `GET` | `/api/admin/customers/` | Customers Page |
| 13 | `PATCH` | `/api/admin/customers/{id}/` | Customers Page |
| 14 | `DELETE` | `/api/admin/customers/{id}/` | Customers Page |

All admin endpoints must require is_staff=True (IsAdminUser permission).
Once you have added these to Django, let me know and I will wire up the frontend immediately.
