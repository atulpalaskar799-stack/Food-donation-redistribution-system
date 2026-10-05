# Food Donation and Redistribution System

Academic B.Sc. Computer Science project using **HTML5 + CSS3 + Vanilla JavaScript**, **Python Flask**, and **MySQL**. The PRD specifies this browser → Flask/API → MySQL architecture and the core food listing → matching → acceptance → pickup → delivery → analytics workflow. 

## 1. Prerequisites

Install:
- Python 3.11+ recommended
- MySQL Server 8.x
- Visual Studio Code
- A modern browser

## 2. Open in VS Code

Extract/open the `food_donation_system` folder in VS Code.

## 3. Create virtual environment

Open VS Code Terminal (PowerShell or CMD):

```powershell
python -m venv venv
venv\Scriptsctivate
pip install -r requirements.txt
```

`venv` isolates project packages. `pip install` installs Flask, MySQL Connector, dotenv, Werkzeug and CORS.

## 4. Configure MySQL

Start MySQL Server. Open MySQL Workbench or the MySQL command line.

Run:

```sql
SOURCE C:/path/to/food_donation_system/database/schema.sql;
```

Use forward slashes in the path, or copy/paste the contents of `schema.sql` into MySQL Workbench.

The schema creates `food_redistribution_db`, all relational tables, indexes, foreign keys and default food categories.

## 5. Configure `.env`

Copy `.env.example` to `.env`.

Example:

```env
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=replace_with_a_long_random_secret
DB_HOST=localhost
DB_PORT=3306
DB_NAME=food_redistribution_db
DB_USER=root
DB_PASSWORD=YOUR_MYSQL_PASSWORD
```

Do not commit `.env` to Git.

## 6. Insert demo data

After activating the virtual environment:

```powershell
python scripts\seed_demo.py
```

This creates secure password hashes, not plain-text database passwords.

### Demo credentials

| Role | Email | Password |
|---|---|---|
| Admin | admin@foodshare.local | Admin@123 |
| Donor | donor@foodshare.local | Donor@123 |
| NGO | ngo@foodshare.local | Ngo@123 |
| Volunteer | volunteer@foodshare.local | Volunteer@123 |

These are development/demo credentials only. Change/remove them before deployment.

## 7. Run Flask

```powershell
python app.py
```

Open:

`http://127.0.0.1:5000`

## 8. Complete demo workflow

1. Login as donor.
2. Create a food donation.
3. Login as NGO.
4. NGO must be verified. The seeded NGO is already verified.
5. Create a requirement.
6. Click **Run Smart Matching**.
7. Accept a suitable match.
8. Login as admin.
9. Assign an active volunteer to the accepted donation (the current UI/API supports assignment; use `/api/assignments` with JSON if testing manually).
10. Login as volunteer.
11. Move assignment through Start → Picked → Out → Delivered.
12. Login as NGO.
13. Confirm the delivered donation.
14. The donation becomes `successfully_redistributed`.
15. Points are awarded once through `point_transactions`.
16. Open Leaderboard to verify ranking.

## 9. API examples

Login:

```http
POST /api/auth/login
Content-Type: application/json

{"email":"donor@foodshare.local","password":"Donor@123"}
```

Run smart matching:

```http
POST /api/matches
```

Assign volunteer as admin:

```json
POST /api/assignments
{"donation_id": 1, "volunteer_id": 4}
```

## 10. Ranking logic

The project uses a database-backed point ledger. The main suggested values from the PRD are:

- Successful food donation: +10
- Meaningful quantity bonus: +5 (configurable extension point)
- Successful NGO fulfillment: +10
- Completed pickup: +5
- Completed delivery: +10
- Fast response: +2 (optional)
- Attributable cancellation after acceptance: -5
- Verified invalid/expired activity: -10

`point_transactions` is the audit ledger. A unique `(user_id, activity_type, reference_id)` constraint plus `INSERT IGNORE` prevents the same activity from being awarded twice.

Leaderboard totals are aggregated from actual point transactions. Categories: Donors, NGOs, Volunteers and Overall. Period filters include all-time, monthly and quarterly.

## 11. Smart Matching

Matching is generated from actual MySQL records. A score out of 100 is calculated using:
- Category compatibility: 40 points
- Quantity compatibility: up to 25 points
- Location text proximity: 20 points
- Time/expiry compatibility: up to 15 points

A match is created only when the score reaches 55 and the donation is not expired. Verified NGO requirements are used. This is intentionally understandable for a B.Sc. viva and can be explained as a weighted rule-based matching algorithm.

## 12. Database relationships

- `users` is the central account table.
- One user has one role-specific profile in `donor_profiles`, `ngo_profiles` or `volunteer_profiles`.
- `donations` belongs to a donor and food category.
- `requirements` belongs to an NGO and food category.
- `matches` connects donations and requirements.
- `assignments` connects an accepted donation to a volunteer.
- `donation_history` audits lifecycle changes.
- `point_transactions` records every ranking point event.
- `rankings` stores optional leaderboard snapshots.
- `notifications` stores user alerts.

## 13. Important lifecycle

Available → Matched → Accepted → Volunteer Assigned → Pickup Started → Picked Up → Out for Delivery → Delivered → Successfully Redistributed

Also supported: Cancelled, Expired and Rejected.

## 14. Testing checklist

- [ ] Register donor
- [ ] Register NGO
- [ ] Register volunteer
- [ ] Login/logout
- [ ] Duplicate email rejected
- [ ] NGO verification
- [ ] Donor creates donation
- [ ] Expired donation rejected
- [ ] NGO creates requirement
- [ ] Unverified NGO cannot accept
- [ ] Smart matching creates real database matches
- [ ] NGO accepts match
- [ ] Admin assigns volunteer
- [ ] Volunteer updates pickup/delivery
- [ ] NGO confirms receipt
- [ ] Donation history updates
- [ ] Points are awarded
- [ ] Duplicate point award is prevented
- [ ] Leaderboard shows points
- [ ] Admin analytics load
- [ ] Notifications are created
- [ ] Role protection blocks unauthorized operations

## 15. Troubleshooting

### `ModuleNotFoundError`
Activate the venv and run:

```powershell
pip install -r requirements.txt
```

### MySQL connection error
Check:
- MySQL Server is running
- `.env` exists
- DB host/port/user/password are correct
- `food_redistribution_db` exists
- `schema.sql` has been executed

### `Unknown database food_redistribution_db`
Run `database/schema.sql`.

### `Table doesn't exist`
Run `database/schema.sql` again after selecting the correct MySQL server.

### Port 5000 is busy
Change the last line of `app.py` to:

```python
app.run(debug=True, port=5001)
```

Then open `http://127.0.0.1:5001`.

## 16. Project structure

```text
food_donation_system/
├── app.py
├── config.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── database/
│   ├── schema.sql
│   └── seed.sql
├── models/
│   ├── __init__.py
│   ├── user.py
│   ├── donation.py
│   ├── requirement.py
│   ├── assignment.py
│   └── ranking.py
├── routes/
│   └── __init__.py
├── scripts/
│   └── seed_demo.py
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── rankings.html
│   ├── donor/
│   ├── ngo/
│   ├── volunteer/
│   └── admin/
├── static/
│   ├── css/style.css
│   └── js/
└── tests/
    └── test_app.py
```

## Academic note

The implementation is deliberately modular but simple enough to explain in a B.Sc. Computer Science viva. It demonstrates HTML/CSS/JavaScript, Flask routes/API communication, MySQL relationships, CRUD, authentication, role authorization, rule-based Smart Matching, lifecycle history, ranking transactions and analytics. It does not include the PRD's out-of-scope payment, government API, live GPS, automatic food-quality certification or advanced AI prediction features.
