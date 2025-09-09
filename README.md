# 🩺 Blood Pressure Tracker (Backend)

A simple Flask + PostgreSQL backend for tracking **blood pressure readings** with authentication and Excel export functionality.

## 🚀 Features
- 🔑 **User Authentication** (Register & Login with password hashing + token-based auth)
- 🩸 **Blood Pressure Management**
  - Add new readings
  - Edit existing readings
  - Delete readings
  - Fetch history
- 📊 **Export to Excel**
  - Download blood pressure readings as `.xlsx`
  - Optional date filters (`start` & `end`)
- 🛡️ **Secure API** with Bearer token authentication
- 🏥 **Health Check API**

---

## 🛠️ Tech Stack
- **Backend**: [Flask](https://flask.palletsprojects.com/)
- **Database**: [PostgreSQL](https://www.postgresql.org/) (via psycopg2)
- **Auth**: Werkzeug security (hashed passwords, token auth)
- **Excel Export**: [OpenPyXL](https://openpyxl.readthedocs.io/)
- **Deployment Ready**: Supabase, Render, Railway, Heroku, etc.

---

## ⚡ Installation

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/yourusername/bp-tracker-backend.git
cd bp-tracker-backend

2️⃣ Create Virtual Environment & Install Dependencies
python3 -m venv venv
source venv/bin/activate   # On Windows use: venv\Scripts\activate
pip install -r requirements.txt

3️⃣ Environment Variables

Create a .env file (or export variables in your shell):

DATABASE_URL=postgresql://<user>:<password>@<host>:5432/<database>
PORT=5000

4️⃣ Run Server
python app.py

📡 API Endpoints
🔐 Authentication

POST /api/register → Register new user

POST /api/login → Login & get token

🩸 Blood Pressure

POST /api/bp → Add a reading

PUT /api/bp/<id> → Update a reading

DELETE /api/bp/<id> → Delete a reading

GET /api/history → Fetch history

📊 Export

GET /api/export?start=YYYY-MM-DD&end=YYYY-MM-DD → Download .xlsx

🏥 Health Check

GET /health

📝 Example Usage (cURL)
# Register
curl -X POST http://localhost:5000/api/register \
  -H "Content-Type: application/json" \
  -d '{"username":"john","password":"secret"}'

# Login
curl -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"john","password":"secret"}'

# Add Reading (replace <TOKEN>)
curl -X POST http://localhost:5000/api/bp \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"systolic":120,"diastolic":80}'

📂 Project Structure
.
├── app.py              # Main Flask app
├── requirements.txt    # Dependencies
├── README.md           # Documentation
└── .env                # Environment variables (not committed)

📦 Dependencies

Create requirements.txt:

Flask
Flask-Cors
psycopg2-binary
openpyxl
werkzeug

🛳️ Deployment

Use Supabase/Postgres for database

Deploy Flask app on Render / Railway / Heroku / Docker

Set DATABASE_URL in environment variables
