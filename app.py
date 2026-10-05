from flask import Flask, render_template, session, redirect, url_for, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
from decimal import Decimal
import mysql.connector
from mysql.connector import Error
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

def db():
    return mysql.connector.connect(host=Config.DB_HOST, port=Config.DB_PORT, user=Config.DB_USER,
                                   password=Config.DB_PASSWORD, database=Config.DB_NAME)

def query(sql, params=(), fetch=True):
    conn=db(); cur=conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        if fetch: return cur.fetchall()
        conn.commit(); return cur.lastrowid
    finally: cur.close(); conn.close()

def execute(sql, params=()): return query(sql, params, False)

def current_user():
    uid=session.get("user_id")
    if not uid: return None
    rows=query("SELECT user_id,name,email,phone,role,status FROM users WHERE user_id=%s",(uid,))
    return rows[0] if rows else None

def login_required(f):
    @wraps(f)
    def wrapper(*a,**kw):
        if not current_user():
            return (jsonify(error="Authentication required"),401) if request.path.startswith("/api/") else redirect(url_for("login"))
        return f(*a,**kw)
    return wrapper

def role_required(*roles):
    def deco(f):
        @wraps(f)
        def wrapper(*a,**kw):
            u=current_user()
            if not u: return jsonify(error="Authentication required"),401
            if u["role"] not in roles: return jsonify(error="Forbidden"),403
            return f(*a,**kw)
        return wrapper
    return deco

def history(did,status,uid,remarks=""):
    execute("INSERT INTO donation_history(donation_id,status,changed_by,remarks) VALUES(%s,%s,%s,%s)",(did,status,uid,remarks))

def notify(uid,title,message):
    execute("INSERT INTO notifications(user_id,title,message) VALUES(%s,%s,%s)",(uid,title,message))

def award(uid,activity,points,ref=None):
    execute("INSERT IGNORE INTO point_transactions(user_id,activity_type,points,reference_id) VALUES(%s,%s,%s,%s)",
            (uid,activity,points,ref))

def expire_old():
    execute("UPDATE donations SET status='expired' WHERE expiry_at<NOW() AND status IN ('available','matched')")
    rows=query("""SELECT donation_id,donor_id FROM donations d WHERE d.status='expired'
                  AND NOT EXISTS (SELECT 1 FROM donation_history h WHERE h.donation_id=d.donation_id AND h.status='expired')""")
    for r in rows:
        history(r["donation_id"],"expired",None,"Automatic expiry")
        award(r["donor_id"],"invalid_or_expired",-10,r["donation_id"])

@app.route("/")
def home(): return render_template("index.html",user=current_user())
@app.route("/login")
def login(): return render_template("login.html")
@app.route("/register")
def register(): return render_template("register.html")
@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("home"))
@app.route("/dashboard")
@login_required
def dashboard():
    return redirect(url_for({"donor":"donor_dashboard","ngo":"ngo_dashboard","volunteer":"volunteer_dashboard","admin":"admin_dashboard"}[current_user()["role"]]))
@app.route("/donor")
@login_required
def donor_dashboard(): return render_template("donor/dashboard.html",user=current_user()) if current_user()["role"]=="donor" else redirect(url_for("dashboard"))
@app.route("/ngo")
@login_required
def ngo_dashboard(): return render_template("ngo/dashboard.html",user=current_user()) if current_user()["role"]=="ngo" else redirect(url_for("dashboard"))
@app.route("/volunteer")
@login_required
def volunteer_dashboard(): return render_template("volunteer/dashboard.html",user=current_user()) if current_user()["role"]=="volunteer" else redirect(url_for("dashboard"))
@app.route("/admin")
@login_required
def admin_dashboard(): return render_template("admin/dashboard.html",user=current_user()) if current_user()["role"]=="admin" else redirect(url_for("dashboard"))
@app.route("/rankings")
@login_required
def rankings_page(): return render_template("rankings.html",user=current_user())
@app.route("/donations/new")
@login_required
def donation_form(): return render_template("donor/donation_form.html",user=current_user())
@app.route("/requirements/new")
@login_required
def requirement_form(): return render_template("ngo/requirement_form.html",user=current_user())

@app.post("/api/auth/register")
def api_register():
    d=request.get_json(silent=True) or request.form
    name=(d.get("name") or "").strip(); email=(d.get("email") or "").strip().lower()
    role=d.get("role") or ""; password=d.get("password") or ""
    if not name or not email or len(password)<6 or role not in ("donor","ngo","volunteer"):
        return jsonify(error="Name, email, role and password (6+ characters) are required"),400
    if query("SELECT user_id FROM users WHERE email=%s",(email,)): return jsonify(error="Email already registered"),409
    uid=execute("INSERT INTO users(name,email,phone,password_hash,role) VALUES(%s,%s,%s,%s,%s)",
                (name,email,d.get("phone"),generate_password_hash(password),role))
    if role=="donor": execute("INSERT INTO donor_profiles(user_id) VALUES(%s)",(uid,))
    elif role=="ngo": execute("INSERT INTO ngo_profiles(user_id,organization_name,address) VALUES(%s,%s,%s)",(uid,d.get("organization_name") or name,d.get("address")))
    else: execute("INSERT INTO volunteer_profiles(user_id,area) VALUES(%s,%s)",(uid,d.get("area")))
    return jsonify(message="Registration successful. NGO accounts require admin verification."),201

@app.post("/api/auth/login")
def api_login():
    d=request.get_json(silent=True) or request.form
    rows=query("SELECT * FROM users WHERE email=%s",((d.get("email") or "").strip().lower(),))
    if not rows or not check_password_hash(rows[0]["password_hash"],d.get("password") or ""): return jsonify(error="Invalid email or password"),401
    if rows[0]["status"]!="active": return jsonify(error="Account is not active"),403
    session["user_id"]=rows[0]["user_id"]; return jsonify(message="Login successful",role=rows[0]["role"],redirect=url_for("dashboard"))

@app.get("/api/me")
@login_required
def me():
    u=current_user(); p=query("SELECT COALESCE(SUM(points),0) points,COUNT(*) activities FROM point_transactions WHERE user_id=%s AND points>0",(u["user_id"],))[0]
    return jsonify(user=u,points=p)

@app.get("/api/categories")
@login_required
def categories(): return jsonify(categories=query("SELECT * FROM food_categories ORDER BY name"))

@app.route("/api/donations",methods=["GET","POST"])
@login_required
def donations_api():
    expire_old(); u=current_user()
    if request.method=="GET":
        if u["role"]=="donor":
            rows=query("""SELECT d.*,c.name category FROM donations d JOIN food_categories c ON c.category_id=d.category_id
                          WHERE d.donor_id=%s ORDER BY d.created_at DESC""",(u["user_id"],))
        elif u["role"]=="ngo":
            rows=query("""SELECT d.*,c.name category,u.name donor_name FROM donations d JOIN food_categories c ON c.category_id=d.category_id
                          JOIN users u ON u.user_id=d.donor_id WHERE d.status IN ('available','matched') AND d.expiry_at>NOW()
                          ORDER BY d.expiry_at""")
        elif u["role"]=="volunteer":
            rows=query("""SELECT d.*,c.name category FROM donations d JOIN food_categories c ON c.category_id=d.category_id
                          JOIN assignments a ON a.donation_id=d.donation_id WHERE a.volunteer_id=%s""",(u["user_id"],))
        else:
            rows=query("""SELECT d.*,c.name category,u.name donor_name FROM donations d JOIN food_categories c ON c.category_id=d.category_id
                          JOIN users u ON u.user_id=d.donor_id ORDER BY d.created_at DESC""")
        return jsonify(donations=rows)
    if u["role"]!="donor": return jsonify(error="Only donors can create donations"),403
    d=request.get_json() or {}
    fields=["category_id","food_name","quantity","unit","prepared_at","expiry_at","pickup_availability","pickup_address"]
    if any(not d.get(x) for x in fields): return jsonify(error="All required fields are required"),400
    try: prepared=datetime.fromisoformat(d["prepared_at"]); expiry=datetime.fromisoformat(d["expiry_at"]); qty=Decimal(str(d["quantity"]))
    except Exception: return jsonify(error="Invalid date or quantity"),400
    if qty<=0 or expiry<=datetime.now(): return jsonify(error="Quantity must be positive and expiry must be future"),400
    did=execute("""INSERT INTO donations(donor_id,category_id,food_name,description,quantity,unit,prepared_at,expiry_at,
                    pickup_availability,pickup_address,notes) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (u["user_id"],d["category_id"],d["food_name"],d.get("description"),qty,d["unit"],prepared,expiry,d["pickup_availability"],d["pickup_address"],d.get("notes")))
    history(did,"available",u["user_id"],"Donation created"); return jsonify(message="Donation created",donation_id=did),201

@app.route("/api/requirements",methods=["GET","POST"])
@login_required
def requirements_api():
    u=current_user()
    if request.method=="GET":
        return jsonify(requirements=query("""SELECT r.*,c.name category,n.organization_name FROM requirements r
                    JOIN food_categories c ON c.category_id=r.category_id JOIN ngo_profiles n ON n.user_id=r.ngo_id ORDER BY r.created_at DESC"""))
    if u["role"]!="ngo": return jsonify(error="Only NGOs can create requirements"),403
    v=query("SELECT verification_status FROM ngo_profiles WHERE user_id=%s",(u["user_id"],))
    if not v or v[0]["verification_status"]!="verified": return jsonify(error="NGO must be verified by admin"),403
    d=request.get_json() or {}; fields=["category_id","quantity_required","unit","needed_by","location"]
    if any(not d.get(x) for x in fields): return jsonify(error="All required fields are required"),400
    try: needed=datetime.fromisoformat(d["needed_by"]); qty=Decimal(str(d["quantity_required"]))
    except Exception: return jsonify(error="Invalid date or quantity"),400
    if qty<=0 or needed<=datetime.now(): return jsonify(error="Quantity must be positive and needed-by must be future"),400
    rid=execute("""INSERT INTO requirements(ngo_id,category_id,quantity_required,unit,needed_by,location,description)
                   VALUES(%s,%s,%s,%s,%s,%s,%s)""",(u["user_id"],d["category_id"],qty,d["unit"],needed,d["location"],d.get("description")))
    return jsonify(message="Requirement created",requirement_id=rid),201

def match_score(d,r):
    s=0
    if d["category_id"]==r["category_id"]: s+=40
    s+=25*min(float(d["quantity"])/float(r["quantity_required"]),1)
    if r["location"].lower() in d["pickup_address"].lower() or d["pickup_address"].lower() in r["location"].lower(): s+=20
    eh=(d["expiry_at"]-datetime.now()).total_seconds()/3600; nh=(r["needed_by"]-datetime.now()).total_seconds()/3600
    if 0<eh<=max(nh,1): s+=15
    elif eh>0: s+=8
    return round(min(s,100),2)

@app.route("/api/matches",methods=["GET","POST"])
@login_required
def matches_api():
    expire_old(); u=current_user()
    if request.method=="POST":
        reqs=query("""SELECT r.* FROM requirements r JOIN ngo_profiles n ON n.user_id=r.ngo_id
                      WHERE r.status='open' AND n.verification_status='verified' AND r.needed_by>NOW()""")
        dons=query("SELECT * FROM donations WHERE status IN ('available','matched') AND expiry_at>NOW()")
        count=0
        for d in dons:
            for r in reqs:
                s=match_score(d,r)
                if s>=55:
                    execute("INSERT IGNORE INTO matches(donation_id,requirement_id,match_score) VALUES(%s,%s,%s)",(d["donation_id"],r["requirement_id"],s)); count+=1
            if any(match_score(d,r)>=55 for r in reqs):
                execute("UPDATE donations SET status='matched' WHERE donation_id=%s AND status='available'",(d["donation_id"],)); history(d["donation_id"],"matched",u["user_id"],"Smart match generated")
        return jsonify(message="Matching completed",matches_created=count)
    return jsonify(matches=query("""SELECT m.*,d.food_name,d.quantity,d.unit,d.pickup_address,d.expiry_at,d.status donation_status,
                  r.quantity_required,r.unit requirement_unit,r.location,r.needed_by,n.organization_name FROM matches m
                  JOIN donations d ON d.donation_id=m.donation_id JOIN requirements r ON r.requirement_id=m.requirement_id
                  JOIN ngo_profiles n ON n.user_id=r.ngo_id ORDER BY m.match_score DESC"""))

@app.post("/api/matches/<int:mid>/accept")
@login_required
def accept_match(mid):
    u=current_user()
    if u["role"]!="ngo": return jsonify(error="Only NGOs can accept"),403
    v=query("SELECT verification_status FROM ngo_profiles WHERE user_id=%s",(u["user_id"],))
    if not v or v[0]["verification_status"]!="verified": return jsonify(error="NGO must be verified"),403
    rows=query("""SELECT m.*,d.status donation_status,d.donor_id,r.ngo_id,r.status req_status FROM matches m
                  JOIN donations d ON d.donation_id=m.donation_id JOIN requirements r ON r.requirement_id=m.requirement_id WHERE m.match_id=%s""",(mid,))
    if not rows: return jsonify(error="Match not found"),404
    m=rows[0]
    if m["ngo_id"]!=u["user_id"] or m["donation_status"] not in ("available","matched") or m["req_status"]!="open": return jsonify(error="Match unavailable"),409
    execute("UPDATE donations SET status='accepted' WHERE donation_id=%s",(m["donation_id"],)); execute("UPDATE requirements SET status='matched' WHERE requirement_id=%s",(m["requirement_id"],))
    history(m["donation_id"],"accepted",u["user_id"],"Accepted by verified NGO"); notify(m["donor_id"],"Donation accepted","A verified NGO accepted your donation.")
    return jsonify(message="Donation accepted")

@app.route("/api/assignments",methods=["GET","POST"])
@login_required
def assignments_api():
    u=current_user()
    if request.method=="GET":
        if u["role"]=="volunteer": rows=query("""SELECT a.*,d.food_name,d.pickup_address,d.status donation_status FROM assignments a
            JOIN donations d ON d.donation_id=a.donation_id WHERE a.volunteer_id=%s ORDER BY a.assigned_at DESC""",(u["user_id"],))
        else: rows=query("""SELECT a.*,d.food_name,d.pickup_address,d.status donation_status,u.name volunteer_name FROM assignments a
            JOIN donations d ON d.donation_id=a.donation_id JOIN users u ON u.user_id=a.volunteer_id ORDER BY a.assigned_at DESC""")
        return jsonify(assignments=rows)
    if u["role"]!="admin": return jsonify(error="Only admin can assign"),403
    d=request.get_json() or {}; did=d.get("donation_id"); vid=d.get("volunteer_id")
    if not did or not vid: return jsonify(error="Donation and volunteer required"),400
    if not query("SELECT user_id FROM users WHERE user_id=%s AND role='volunteer' AND status='active'",(vid,)): return jsonify(error="Invalid volunteer"),400
    if not query("SELECT donation_id FROM donations WHERE donation_id=%s AND status='accepted'",(did,)): return jsonify(error="Donation must be accepted"),400
    if query("SELECT assignment_id FROM assignments WHERE donation_id=%s",(did,)): return jsonify(error="Already assigned"),409
    aid=execute("INSERT INTO assignments(donation_id,volunteer_id) VALUES(%s,%s)",(did,vid)); execute("UPDATE donations SET status='volunteer_assigned' WHERE donation_id=%s",(did,))
    history(did,"volunteer_assigned",u["user_id"],"Volunteer assigned"); notify(vid,"New assignment","A pickup/delivery task was assigned to you.")
    return jsonify(message="Assigned",assignment_id=aid),201

@app.post("/api/assignments/<int:aid>/status")
@login_required
def assignment_status(aid):
    u=current_user(); d=request.get_json() or {}; action=d.get("action")
    rows=query("""SELECT a.*,x.donor_id FROM assignments a JOIN donations x ON x.donation_id=a.donation_id WHERE a.assignment_id=%s""",(aid,))
    if not rows: return jsonify(error="Assignment not found"),404
    a=rows[0]
    if u["role"]!="volunteer" or a["volunteer_id"]!=u["user_id"]: return jsonify(error="Forbidden"),403
    trans={"pickup_started":("pickup_status","pickup_started"),"picked_up":("pickup_status","picked_up"),
           "out_for_delivery":("delivery_status","out_for_delivery"),"delivered":("delivery_status","delivered")}
    if action not in trans: return jsonify(error="Invalid action"),400
    col,val=trans[action]; execute(f"UPDATE assignments SET {col}=%s WHERE assignment_id=%s",(val,aid))
    execute("UPDATE donations SET status=%s WHERE donation_id=%s",(val,a["donation_id"])); history(a["donation_id"],val,u["user_id"],"Volunteer status update")
    if action=="picked_up": award(u["user_id"],"completed_pickup",5,aid)
    if action=="delivered": award(u["user_id"],"completed_delivery",10,aid)
    return jsonify(message="Status updated")

@app.post("/api/donations/<int:did>/confirm")
@login_required
def confirm(did):
    u=current_user()
    if u["role"]!="ngo": return jsonify(error="Only NGO can confirm"),403
    rows=query("""SELECT d.*,r.ngo_id FROM donations d JOIN matches m ON m.donation_id=d.donation_id JOIN requirements r ON r.requirement_id=m.requirement_id
                  WHERE d.donation_id=%s AND r.ngo_id=%s AND d.status='delivered'""",(did,u["user_id"]))
    if not rows: return jsonify(error="Donation is not ready for confirmation"),409
    d=rows[0]; execute("UPDATE donations SET status='successfully_redistributed' WHERE donation_id=%s",(did,))
    execute("UPDATE requirements SET status='fulfilled' WHERE requirement_id IN (SELECT requirement_id FROM matches WHERE donation_id=%s) AND ngo_id=%s",(did,u["user_id"]))
    history(did,"successfully_redistributed",u["user_id"],"NGO confirmed receipt")
    award(d["donor_id"],"successful_food_donation",10,did); award(u["user_id"],"successful_ngo_fulfillment",10,did)
    return jsonify(message="Receipt confirmed and redistribution successful")

@app.post("/api/volunteer/availability")
@role_required("volunteer")
def availability():
    u=current_user(); d=request.get_json() or {}
    if d.get("availability") not in ("available","unavailable"): return jsonify(error="Invalid availability"),400
    execute("UPDATE volunteer_profiles SET availability=%s,area=%s WHERE user_id=%s",(d["availability"],d.get("area"),u["user_id"]))
    return jsonify(message="Availability updated")

@app.post("/api/ngo/verify")
@role_required("admin")
def verify_ngo():
    d=request.get_json() or {}
    if d.get("status") not in ("verified","rejected"): return jsonify(error="Invalid status"),400
    execute("UPDATE ngo_profiles SET verification_status=%s WHERE user_id=%s",(d["status"],d.get("user_id")))
    notify(d.get("user_id"),"Verification update",f"NGO verification status: {d['status']}")
    return jsonify(message="Verification updated")

@app.route("/api/profile",methods=["GET","PUT"])
@login_required
def profile():
    u=current_user()
    if request.method=="GET":
        if u["role"]=="donor": p=(query("SELECT * FROM donor_profiles WHERE user_id=%s",(u["user_id"],)) or [{}])[0]
        elif u["role"]=="ngo": p=(query("SELECT * FROM ngo_profiles WHERE user_id=%s",(u["user_id"],)) or [{}])[0]
        else: p=(query("SELECT * FROM volunteer_profiles WHERE user_id=%s",(u["user_id"],)) or [{}])[0]
        return jsonify(user=u,profile=p)
    d=request.get_json() or {}; execute("UPDATE users SET name=%s,phone=%s WHERE user_id=%s",(d.get("name",u["name"]),d.get("phone",u["phone"]),u["user_id"]))
    if u["role"]=="donor": execute("UPDATE donor_profiles SET organization_name=%s,address=%s WHERE user_id=%s",(d.get("organization_name"),d.get("address"),u["user_id"]))
    elif u["role"]=="ngo": execute("UPDATE ngo_profiles SET organization_name=%s,address=%s WHERE user_id=%s",(d.get("organization_name"),d.get("address"),u["user_id"]))
    else: execute("UPDATE volunteer_profiles SET area=%s WHERE user_id=%s",(d.get("area"),u["user_id"]))
    return jsonify(message="Profile updated")

@app.get("/api/notifications")
@login_required
def notifications(): return jsonify(notifications=query("SELECT * FROM notifications WHERE user_id=%s ORDER BY created_at DESC",(current_user()["user_id"],)))

@app.get("/api/rankings")
@login_required
def ranking_api():
    category=request.args.get("category","overall"); period=request.args.get("period","all_time")
    if category not in ("overall","donor","ngo","volunteer"): return jsonify(error="Invalid category"),400
    role_clause=""; params=[]
    if category!="overall": role_clause="AND u.role=%s"; params.append(category)
    period_clause=""
    if period=="monthly": period_clause="AND pt.created_at>=DATE_FORMAT(CURRENT_DATE,'%Y-%m-01')"
    elif period=="quarterly": period_clause="AND pt.created_at>=DATE_SUB(CURRENT_DATE,INTERVAL 3 MONTH)"
    rows=query(f"""SELECT u.user_id,u.name,u.role,COALESCE(SUM(CASE WHEN pt.points>0 THEN pt.points ELSE 0 END),0) points,
                   COUNT(CASE WHEN pt.points>0 THEN 1 END) successful_activities FROM users u
                   LEFT JOIN point_transactions pt ON pt.user_id=u.user_id {period_clause}
                   WHERE u.status='active' {role_clause} GROUP BY u.user_id,u.name,u.role
                   ORDER BY points DESC,successful_activities DESC,u.created_at ASC""",params)
    for i,r in enumerate(rows,1): r["rank"]=i
    return jsonify(rankings=rows)

@app.get("/api/analytics")
@role_required("admin")
def analytics():
    queries={"total_users":"SELECT COUNT(*) n FROM users","donors":"SELECT COUNT(*) n FROM users WHERE role='donor'",
    "ngos":"SELECT COUNT(*) n FROM users WHERE role='ngo'","volunteers":"SELECT COUNT(*) n FROM users WHERE role='volunteer'",
    "donations":"SELECT COUNT(*) n FROM donations","quantity_donated":"SELECT COALESCE(SUM(quantity),0) n FROM donations",
    "redistributed_quantity":"SELECT COALESCE(SUM(quantity),0) n FROM donations WHERE status='successfully_redistributed'",
    "pending":"SELECT COUNT(*) n FROM donations WHERE status IN ('available','matched','accepted','volunteer_assigned','pickup_started','picked_up','out_for_delivery')",
    "delivered":"SELECT COUNT(*) n FROM donations WHERE status IN ('delivered','successfully_redistributed')","expired":"SELECT COUNT(*) n FROM donations WHERE status='expired'",
    "cancelled":"SELECT COUNT(*) n FROM donations WHERE status='cancelled'","successful":"SELECT COUNT(*) n FROM donations WHERE status='successfully_redistributed'"}
    stats={k:query(v)[0]["n"] for k,v in queries.items()}; stats["fulfillment_rate"]=round(stats["successful"]/stats["donations"]*100,2) if stats["donations"] else 0
    stats["delivery_success_rate"]=stats["fulfillment_rate"]
    trends=query("SELECT DATE(created_at) day,COUNT(*) donations FROM donations GROUP BY DATE(created_at) ORDER BY day DESC LIMIT 14")
    cats=query("""SELECT c.name,COUNT(d.donation_id) total FROM food_categories c LEFT JOIN donations d ON d.category_id=c.category_id
                  GROUP BY c.category_id,c.name ORDER BY total DESC""")
    return jsonify(stats=stats,trends=trends,categories=cats)

@app.get("/api/admin/users")
@role_required("admin")
def admin_users(): return jsonify(users=query("""SELECT u.user_id,u.name,u.email,u.phone,u.role,u.status,u.created_at,n.organization_name,n.verification_status
                                                FROM users u LEFT JOIN ngo_profiles n ON n.user_id=u.user_id ORDER BY u.created_at DESC"""))

@app.post("/api/admin/users/<int:uid>/status")
@role_required("admin")
def set_user_status(uid):
    s=(request.get_json() or {}).get("status")
    if s not in ("active","inactive","blocked"): return jsonify(error="Invalid status"),400
    execute("UPDATE users SET status=%s WHERE user_id=%s",(s,uid)); return jsonify(message="User status updated")

@app.post("/api/admin/categories")
@role_required("admin")
def add_category():
    d=request.get_json() or {}; name=(d.get("name") or "").strip()
    if not name: return jsonify(error="Name required"),400
    try: cid=execute("INSERT INTO food_categories(name,description) VALUES(%s,%s)",(name,d.get("description")))
    except Error: return jsonify(error="Category already exists"),409
    return jsonify(category_id=cid),201


@app.post("/api/donations/<int:did>/cancel")
@login_required
def cancel_donation(did):
    u=current_user()
    rows=query("SELECT * FROM donations WHERE donation_id=%s",(did,))
    if not rows:return jsonify(error="Donation not found"),404
    d=rows[0]
    if d["donor_id"]!=u["user_id"] and u["role"]!="admin":return jsonify(error="Forbidden"),403
    if d["status"] not in ("available","matched","accepted"):return jsonify(error="Donation cannot be cancelled at this stage"),409
    execute("UPDATE donations SET status='cancelled' WHERE donation_id=%s",(did,))
    history(did,"cancelled",u["user_id"],"Donation cancelled")
    if d["status"]=="accepted": award(u["user_id"],"cancellation_after_acceptance",-5,did)
    return jsonify(message="Donation cancelled")

@app.get("/matching")
@login_required
def matching_page(): return render_template("matching.html",user=current_user())

@app.get("/assignments")
@login_required
def assignments_page(): return render_template("assignments.html",user=current_user())

@app.get("/profile")
@login_required
def profile_page(): return render_template("profile.html",user=current_user())

@app.get("/notifications")
@login_required
def notifications_page(): return render_template("notifications.html",user=current_user())

@app.errorhandler(Error)
def mysql_error(e): return jsonify(error="Database error. Check MySQL configuration/schema."),500

@app.context_processor
def inject(): return {"current_user":current_user()}

if __name__=="__main__": app.run(debug=True)
