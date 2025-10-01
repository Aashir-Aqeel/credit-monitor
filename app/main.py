import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
load_dotenv()
from app.utils.database import remaining_balance_collection, email_address_collection
from app.services.monitor import check_user_credits
from app.services.monitor import run_monitor
from datetime import datetime



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
    remaining_balance_collection: float
    threshold: float

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
        # Delete any previous balance document (keep only one)
        await remaining_balance_collection.delete_many({})

        # Initialize last_usage_value and last_checked_timestamp
        initial_doc = {
            "remaining_credits": data.remaining_balance_collection,
            "threshold": data.threshold,
            "last_usage_value": 0.0,  # first API hit will update this
            "last_checked": None,
            "last_checked_timestamp": int(datetime.now().timestamp())  # use current timestamp
        }

        result = await remaining_balance_collection.insert_one(initial_doc)
        logger.info(f"Balance updated → {data.remaining_balance_collection}, threshold: {data.threshold}")
        return {"status": "success", "balance_id": str(result.inserted_id)}
    except Exception as e:
        logger.error(f"Error updating balance: {e}")
        raise HTTPException(status_code=500, detail="Failed to update balance")



@app.get("/balance")
async def get_balance():
    """Get current balance and threshold"""
    doc = await remaining_balance_collection.find_one()
    if not doc:
        raise HTTPException(status_code=404, detail="No balance found")
    return {
        "remaining_balance_collection": doc.get("remaining_credits", 0),
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
    scheduler.add_job(run_monitor, "interval", minutes=1)  # 🔥 every 6 hours
    scheduler.start()
    logger.info("Scheduler started (runs every 6 hours)")


@app.on_event("shutdown")
async def shutdown_scheduler():
    scheduler.shutdown()
    logger.info("Scheduler shutdown")
