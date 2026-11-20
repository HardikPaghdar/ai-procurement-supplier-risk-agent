# AI Procurement & Supplier Risk Agent

A FastAPI decision-support demo for manufacturers. It scores supplier delivery/quality risk, identifies purchase orders that may threaten production, ranks qualified alternatives, and drafts manager-reviewed actions.

## Run
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```
API docs: http://127.0.0.1:8000/docs

## Example
```bash
curl http://127.0.0.1:8000/api/suppliers/risk
curl http://127.0.0.1:8000/api/purchase-orders/PO-1003/impact
curl -X POST http://127.0.0.1:8000/api/action-plans -H "Content-Type: application/json" -d '{"purchase_order_id":"PO-1003"}'
```

## Workflow
Supplier and PO history → explainable risk factors → production impact → qualified alternatives → action-plan draft → explicit manager approval.

## API
- GET `/health`, `/api/overview`, `/api/suppliers`, `/api/suppliers/risk`, `/api/purchase-orders`
- GET `/api/suppliers/{id}`, `/api/purchase-orders/{id}/impact`
- POST `/api/action-plans`, `/api/action-plans/{id}/decision`

## Limitations
Deterministic explainable rules, not a trained ML model. Synthetic JSON data; in-memory action state; sample dates anchored to 2026-11-20. No ERP/MRP integration, supplier messaging, PO issuance, capacity reservation, authentication, or database. Validate decisions with procurement and production teams before real use.
