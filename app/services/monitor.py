import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import time
from app.utils.openai_utils import get_openai_usage
from app.utils.database import remaining_credits, usage_collection  # your collections

logger = logging.getLogger(__name__)

def get_utc_day_bucket():
    """Returns Unix timestamps aligned to previous UTC day"""
    now_utc = datetime.utcnow()
    start_utc = datetime(now_utc.year, now_utc.month, now_utc.day) - timedelta(days=1)
    end_utc = start_utc + timedelta(days=1)
    start_ts = int(start_utc.timestamp())
    end_ts = int(end_utc.timestamp())
    return start_ts, end_ts



logger = logging.getLogger(__name__)

import logging
import time
from app.utils.openai_utils import get_openai_usage
from app.utils.database import remaining_credits, usage_collection

logger = logging.getLogger(__name__)

async def check_user_credits():
    logger.info("Starting check_user_credits job...")

    # Fetch last saved usage document
    last_usage_doc = await usage_collection.find_one(sort=[("timestamp", -1)])
    last_saved_response = last_usage_doc.get("response") if last_usage_doc else None

    # Fetch current usage from OpenAI (full response, not just a float)
    usage_response = await get_openai_usage()
    if not usage_response:
        logger.warning("No usage returned from OpenAI")
        return

    logger.info(f"OpenAI usage fetched: {usage_response}")

    # Calculate incremental usage
    usage_diff = 0
    try:
        # Sum amounts for last saved response
        last_total = sum(
            bucket["results"][0]["amount"]["value"]
            for bucket in last_saved_response.get("data", [])
        ) if last_saved_response else 0

        # Sum amounts for current response
        current_total = sum(
        bucket["results"][0]["amount"]["value"]
        for bucket in usage_response.get("data", [])
        )


        usage_diff = max(current_total - last_total, 0)
        logger.info(f"Incremental usage since last check: ${usage_diff}")

    except Exception as e:
        logger.warning(f"Failed to calculate incremental usage: {e}")
        usage_diff = 0

    # Save current usage response
    await usage_collection.insert_one({
        "timestamp": int(time.time()),
        "response": usage_response
    })
    logger.info("Saved usage response to database")

    # Update remaining balance
    balance_doc = await remaining_credits.find_one()
    if balance_doc:
        new_balance = balance_doc.get("remaining_credits", 0) - usage_diff
        await remaining_credits.update_one(
            {"_id": balance_doc["_id"]},
            {"$set": {"remaining_credits": new_balance}}
        )
        logger.info(f"Remaining balance updated → {new_balance}")
    else:
        # Initialize remaining balance if first-time
        initial_balance = 1000  # Set your initial starting balance
        await remaining_credits.insert_one({
            "remaining_credits": initial_balance,
        })
        logger.info(f"Inserted first balance record → {initial_balance}")



# Scheduler
scheduler = AsyncIOScheduler()
scheduler.add_job(check_user_credits, "interval", minutes=0.5)
scheduler.start()
