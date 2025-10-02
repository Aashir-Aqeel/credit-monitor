import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
load_dotenv()
from app.utils.database import remaining_credits, email_address_collection
from app.services.monitor import check_user_credits
from datetime import datetime
from typing import Optional



# ---------------------------------------------------------
# Logging setup
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("credit-monitor")

# ---------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------
app = FastAPI(title="API Credit Monitor")

# ---------------------------------------------------------
# Models
# ---------------------------------------------------------

class BalanceInput(BaseModel):
    remaining_credits: Optional[float] = None
    threshold: Optional[float] = None  # ✅ Make it optional with default


class EmailInput(BaseModel):
    email: str

# ---------------------------------------------------------
# Routes
# ---------------------------------------------------------
@app.get("/")
async def root():
    return {"message": "API Credit Monitor running"}

@app.post("/update-balance")
async def update_balance(data: BalanceInput):
    """Update remaining balance & threshold in DB and initialize usage tracking"""
    try:
        # Get the existing balance document (assuming only one exists)
        existing_doc = await remaining_credits.find_one({})

        if existing_doc is None:
            # If no document exists, create one with defaults
            initial_doc = {
                "remaining_credits": data.remaining_credits if data.remaining_credits is not None else 0.0,
                "threshold": data.threshold if data.threshold is not None else 0.0,
                "last_usage_value": 0.0,
                "last_checked": None,
                "last_checked_timestamp": int(datetime.now().timestamp())
            }
            result = await remaining_credits.insert_one(initial_doc)
            logger.info(f"Balance initialized → {initial_doc}")
            return {"status": "success", "balance_id": str(result.inserted_id)}

        # Prepare update dict with only provided fields
        update_dict = {}
        if data.remaining_credits is not None:
            update_dict["remaining_credits"] = data.remaining_credits
        if data.threshold is not None:
            update_dict["threshold"] = data.threshold
        update_dict["last_checked_timestamp"] = int(datetime.now().timestamp())

        # Update the document
        await remaining_credits.update_one(
            {"_id": existing_doc["_id"]},
            {"$set": update_dict}
        )
        logger.info(f"Balance updated → {update_dict}")
        return {"status": "success", "updated_fields": update_dict}

    except Exception as e:
        logger.error(f"Error updating balance: {e}")
        raise HTTPException(status_code=500, detail="Failed to update balance")
 



@app.get("/balance")
async def get_balance():
    """Get current balance and threshold"""
    doc = await remaining_credits.find_one()
    if not doc:
        raise HTTPException(status_code=404, detail="No balance found")
    return {
        "remaining_credits": doc.get("remaining_credits", 0),
        "threshold": doc.get("threshold", 0),
    }

@app.post("/add-email")
async def add_email(data: EmailInput):
    """Add an email to receive alerts"""
    try:
        result = await email_address_collection.insert_one({"email": data.email})
        logger.info(f"Email added for alerts → {data.email}")
        return {"status": "success", "email_id": str(result.inserted_id)}
    except Exception as e:
        logger.error(f"Error adding email: {e}")
        raise HTTPException(status_code=500, detail="Failed to add email")

@app.get("/emails")
async def list_emails():
    """List all alert emails"""
    emails = await email_address_collection.find().to_list(length=100)
    return {"emails": [doc["email"] for doc in emails]}

# ---------------------------------------------------------
# Scheduler setup
# ---------------------------------------------------------
scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def start_scheduler():
    scheduler.add_job(check_user_credits, "interval", minutes=1)  # 🔥 every 6 hours
    scheduler.start()
    logger.info("Scheduler started (runs every 6 hours)")


@app.on_event("shutdown")
async def shutdown_scheduler():
    scheduler.shutdown()
    logger.info("Scheduler shutdown")
