import os
import sys

# Add the main project folder to Python's import path
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)
sys.path.insert(0, PROJECT_ROOT)

from app import db
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

def q(c,sql,p=(),fetch=False):
    cur=c.cursor(dictionary=True);cur.execute(sql,p)
    if fetch:return cur.fetchall()
    c.commit();return cur.lastrowid

c=db()
users=[
("Admin User","admin@foodshare.local","9999999999","Admin@123","admin"),
("Demo Donor","donor@foodshare.local","9000000001","Donor@123","donor"),
("Helping Hands NGO","ngo@foodshare.local","9000000002","Ngo@123","ngo"),
("Demo Volunteer","volunteer@foodshare.local","9000000003","Volunteer@123","volunteer")]
for name,email,phone,pw,role in users:
    if not q(c,"SELECT user_id FROM users WHERE email=%s",(email,),True):
        uid=q(c,"INSERT INTO users(name,email,phone,password_hash,role) VALUES(%s,%s,%s,%s,%s)",(name,email,phone,generate_password_hash(pw),role))
        if role=="donor": q(c,"INSERT INTO donor_profiles(user_id,address) VALUES(%s,%s)",(uid,"Kothrud, Pune"))
        elif role=="ngo": q(c,"INSERT INTO ngo_profiles(user_id,organization_name,verification_status,address) VALUES(%s,%s,'verified',%s)",(uid,"Helping Hands NGO","Kothrud, Pune"))
        elif role=="volunteer": q(c,"INSERT INTO volunteer_profiles(user_id,availability,area) VALUES(%s,'available',%s)",(uid,"Kothrud"))
ids={r["email"]:r["user_id"] for r in q(c,"SELECT user_id,email FROM users WHERE email IN (%s,%s,%s,%s)",tuple(x[1] for x in users),True)}
cat=q(c,"SELECT category_id FROM food_categories WHERE name='Cooked Meals'",fetch=True)[0]["category_id"]
future=datetime.now()+timedelta(hours=10)
did=q(c,"INSERT INTO donations(donor_id,category_id,food_name,description,quantity,unit,prepared_at,expiry_at,pickup_availability,pickup_address) VALUES(%s,%s,'Demo Biryani','Sample food for viva/demo',20,'meals',%s,%s,'5 PM - 8 PM','Kothrud, Pune')",(ids["donor@foodshare.local"],cat,datetime.now(),future))
q(c,"INSERT INTO donation_history(donation_id,status,changed_by,remarks) VALUES(%s,'available',%s,'Seed demo donation')",(did,ids["donor@foodshare.local"]))
rid=q(c,"INSERT INTO requirements(ngo_id,category_id,quantity_required,unit,needed_by,location,description) VALUES(%s,%s,15,'meals',%s,'Kothrud, Pune','Demo NGO requirement')",(ids["ngo@foodshare.local"],cat,future+timedelta(hours=2)))
# Create a demo match and assignment so the academic demo has records to inspect.
m=q(c,"SELECT match_id FROM matches WHERE donation_id=%s AND requirement_id=%s",(did,rid),True)
if not m:
    mid=q(c,"INSERT INTO matches(donation_id,requirement_id,match_score) VALUES(%s,%s,85)",(did,rid))
else: mid=m[0]["match_id"]
q(c,"UPDATE donations SET status='accepted' WHERE donation_id=%s",(did,))
q(c,"UPDATE requirements SET status='matched' WHERE requirement_id=%s",(rid,))
aid=q(c,"SELECT assignment_id FROM assignments WHERE donation_id=%s",(did,),True)
if not aid:
    q(c,"INSERT INTO assignments(donation_id,volunteer_id) VALUES(%s,%s)",(did,ids["volunteer@foodshare.local"]))
q(c,"INSERT IGNORE INTO point_transactions(user_id,activity_type,points,reference_id) VALUES(%s,'demo_completed_pickup',5,%s)",(ids["volunteer@foodshare.local"],did))
q(c,"INSERT IGNORE INTO point_transactions(user_id,activity_type,points,reference_id) VALUES(%s,'demo_contribution',10,%s)",(ids["donor@foodshare.local"],did))
print("Demo data ready.")
print("Admin: admin@foodshare.local / Admin@123")
print("Donor: donor@foodshare.local / Donor@123")
print("NGO: ngo@foodshare.local / Ngo@123")
print("Volunteer: volunteer@foodshare.local / Volunteer@123")
c.close()
