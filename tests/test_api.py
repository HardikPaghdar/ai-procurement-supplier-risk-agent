from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)

def test_overview_and_health():
    assert c.get("/health").json()["status"]=="ok"
    x=c.get("/api/overview").json()
    assert x["supplier_count"]==4 and x["open_purchase_orders"]==3

def test_risk_explanations():
    rows=c.get("/api/suppliers/risk").json()
    assert rows[0]["supplier_id"]=="SUP-03"
    assert all(len(x["factors"])==4 for x in rows)

def test_qualified_alternatives_and_production_risk():
    x=c.get("/api/purchase-orders/PO-1003/impact").json()
    assert x["production_at_risk"] is True
    assert all(a["supplier_id"]!="SUP-04" for a in x["alternative_suppliers"])

def test_approval_state_machine():
    p=c.post("/api/action-plans",json={"purchase_order_id":"PO-1003"})
    assert p.status_code==201 and p.json()["status"]=="pending_approval"
    pid=p.json()["id"]
    d=c.post(f"/api/action-plans/{pid}/decision",json={"decision":"approved","reviewer":"Procurement Lead"})
    assert d.json()["status"]=="approved"
    assert c.post(f"/api/action-plans/{pid}/decision",json={"decision":"rejected","reviewer":"Lead"}).status_code==409

def test_missing_order():
    assert c.get("/api/purchase-orders/nope/impact").status_code==404
