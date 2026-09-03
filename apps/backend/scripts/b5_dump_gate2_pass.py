import asyncio, sys, json
sys.path.insert(0, ".")
import pickle
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models.raw_evidence import RawEvidence


async def main():
    with open("b5_gate2_results.pkl", "rb") as f:
        outcomes = pickle.load(f)
    passed = [o for o in outcomes if o["status"] == "PASS"]
    async with AsyncSessionLocal() as db:
        with open("b5_gate2_pass_detail.txt", "w", encoding="utf-8") as out:
            out.write(f"PASS count: {len(passed)}\n\n")
            for o in passed:
                out.write(f"RSS TITLE: {o['title']}\n")
                out.write(f"  entity={o['entity_id']} category={o['category']} method={o['method']}\n")
                row = (await db.execute(select(RawEvidence.title, RawEvidence.published_at, RawEvidence.raw_payload)
                                         .where(RawEvidence.id == o["evidence_id"]))).first()
                if row:
                    payload = json.loads(row.raw_payload) if row.raw_payload else {}
                    out.write(f"  MATCHED NSE TITLE: {row.title}\n")
                    out.write(f"  NSE desc: {payload.get('desc')}  published_at: {row.published_at}\n")
                    out.write(f"  NSE attchmntText: {payload.get('attchmntText','')}\n")
                out.write("\n")
    print("done")


asyncio.run(main())
