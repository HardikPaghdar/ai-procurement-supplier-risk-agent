import json
from datetime import date
from pathlib import Path
from uuid import uuid4
from typing import Literal
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

D=json.loads((Path(__file__).resolve().parents[1]/"data.json").read_text())
S,O,DEL,Q=D["suppliers"],D["orders"],D["deliveries"],D["quality"]
PLANS={}
app=FastAPI(title="AI Procurement & Supplier Risk Agent",version="1.0.0",description="Explainable supplier risk and human-approved procurement decision support.")

def risk(s):
    ds=[x for x in DEL if x[0]==s["id"]]; qs=[x for x in Q if x["supplier_id"]==s["id"]]
    ontime=sum(x[1] for x in ds)/len(ds) if ds else 1
    defect=sum(x["bad"] for x in qs)/max(1,sum(x["checked"] for x in qs))
    open_orders=[o for o in O if o["supplier_id"]==s["id"] and o["status"]=="open"]
    exposure=min(1,sum(o["value"] for o in open_orders)/100000)
    majors=sum(x["severity"] in ("major","critical") for x in qs)
    parts=[(1-ontime)*45,min(1,defect/.08)*30,exposure*15,min(1,majors/3)*10]
    score=round(min(100,sum(parts)),1)
    return {"supplier_id":s["id"],"supplier_name":s["name"],"risk_score":score,
      "risk_band":"high" if score>=60 else "medium" if score>=30 else "low",
      "on_time_rate":round(ontime,3),"defect_rate":round(defect,4),
      "factors":[
       {"factor":"late_delivery_rate","contribution":round(parts[0],1),"evidence":f"{(1-ontime)*100:.1f}% late across {len(ds)} deliveries"},
       {"factor":"quality_defect_rate","contribution":round(parts[1],1),"evidence":f"{defect*100:.2f}% defective units"},
       {"factor":"open_order_exposure","contribution":round(parts[2],1),"evidence":f"{len(open_orders)} open orders worth {sum(o['value'] for o in open_orders):.0f}"},
       {"factor":"major_quality_incidents","contribution":round(parts[3],1),"evidence":f"{majors} major/critical incidents"}]}

def alternatives(o):
    out=[]
    for s in S:
        if s["id"]==o["supplier_id"] or not s["qualified"] or o["part"] not in s["parts"]: continue
        cap=s["capacity"]-s["committed"]
        if cap<o["qty"]: continue
        r=risk(s); delta=(s["price"]-o["unit_price"])/o["unit_price"]
        rank=.45*r["risk_score"]+.30*min(100,s["lead"]*5)+.25*max(-20,min(100,delta*100))
        out.append({"supplier_id":s["id"],"supplier_name":s["name"],"risk_score":r["risk_score"],"lead_time_days":s["lead"],"unit_price":s["price"],"available_capacity":cap,"price_change_pct":round(delta*100,1),"ranking_score":round(rank,1)})
    return sorted(out,key=lambda x:x["ranking_score"])

def impact(o):
    s=next(x for x in S if x["id"]==o["supplier_id"])
    days=(date.fromisoformat(o["required_by"])-date(2026,11,20)).days
    lead=max(s["lead"],o["promised_days"]); cover=o["stock"]//max(1,o["daily_use"])
    at_risk=lead>days+cover
    return {"purchase_order_id":o["id"],"part_id":o["part"],"supplier_id":s["id"],"supplier_name":s["name"],"required_by":o["required_by"],"days_until_required":days,"estimated_lead_time_days":lead,"stock_cover_days":cover,"production_at_risk":at_risk,"risk_reason":"Expected replenishment may arrive after stock cover is exhausted." if at_risk else "Lead-time estimate is within current stock buffer.","supplier_risk":risk(s),"alternative_suppliers":alternatives(o)}

class PlanIn(BaseModel):
    purchase_order_id:str
class Decision(BaseModel):
    decision:Literal["approved","rejected"]
    reviewer:str=Field(min_length=2,max_length=80)
    note:str=Field(default="",max_length=500)

@app.get("/health")
def health(): return {"status":"ok"}
@app.get("/api/overview")
def overview():
    scores=[risk(s) for s in S]; impacts=[impact(o) for o in O if o["status"]=="open"]
    return {"supplier_count":len(S),"high_risk_suppliers":sum(x["risk_band"]=="high" for x in scores),"open_purchase_orders":len(impacts),"open_order_value":sum(o["value"] for o in O if o["status"]=="open"),"production_at_risk_orders":sum(x["production_at_risk"] for x in impacts)}
@app.get("/api/suppliers")
def suppliers(): return S
@app.get("/api/suppliers/risk")
def supplier_risks(): return sorted([risk(s) for s in S],key=lambda x:x["risk_score"],reverse=True)
@app.get("/api/suppliers/{sid}")
def supplier(sid:str):
    s=next((x for x in S if x["id"]==sid),None)
    if not s: raise HTTPException(404,"Supplier not found")
    return {"supplier":s,"risk":risk(s)}
@app.get("/api/purchase-orders")
def orders(): return O
@app.get("/api/purchase-orders/{oid}/impact")
def order_impact(oid:str):
    o=next((x for x in O if x["id"]==oid),None)
    if not o: raise HTTPException(404,"Purchase order not found")
    return impact(o)
@app.post("/api/action-plans",status_code=201)
def create_plan(req:PlanIn):
    o=next((x for x in O if x["id"]==req.purchase_order_id),None)
    if not o: raise HTTPException(404,"Purchase order not found")
    i=impact(o); actions=[]
    if i["production_at_risk"]:
        actions=["Contact current supplier for a confirmed recovery date"]
        if i["alternative_suppliers"]: actions.append("Request feasibility and quote check from "+i["alternative_suppliers"][0]["supplier_name"])
        actions.append("Review stock allocation and production sequence with planning")
    else: actions=["Monitor supplier milestone and confirm dispatch before required-by date"]
    p={"id":str(uuid4()),"purchase_order_id":o["id"],"status":"pending_approval","production_at_risk":i["production_at_risk"],"actions":actions,"evidence":i["risk_reason"],"reviewer":None,"approval_note":None}
    PLANS[p["id"]]=p; return p
@app.post("/api/action-plans/{pid}/decision")
def decide(pid:str,req:Decision):
    p=PLANS.get(pid)
    if not p: raise HTTPException(404,"Action plan not found")
    if p["status"]!="pending_approval": raise HTTPException(409,"Action plan already reviewed")
    p.update(status=req.decision,reviewer=req.reviewer,approval_note=req.note); return p
@app.get("/api/action-plans")
def plans(): return list(PLANS.values())
