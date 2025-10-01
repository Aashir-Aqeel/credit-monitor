import os
import asyncio
import httpx
import logging
from datetime import datetime
from app.utils.database import remaining_balance_collection, email_address_collection
from app.utils.email_utils import send_email  # import your email function

# Terminal logger
logger = logging.getLogger("credit-monitor")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY not found in environment variables!")

HEADERS = {
    "Authorization": f"Bearer {OPENAI_API_KEY}"
}

# Threshold for sending alerts
THRESHOLD = 10.0  # Example value

async def check_user_credits():
    """
    Check OpenAI API usage, update remaining balance, and send alerts if below threshold.
    """
    try:
        logger.info("Running OpenAI cost monitor...")

        # Fetch last saved balance
        balance_doc = await remaining_balance_collection.find_one()
        if not balance_doc:
            logger.warning("No balance found in DB. Set initial balance via /update-balance API.")
            return

        last_balance = balance_doc.get("remaining_credits", 0)
        last_api_value = balance_doc.get("last_api_value", 0)

        # Call OpenAI API
        async with httpx.AsyncClient(timeout=30.0) as client:
            start_time = int(datetime.utcnow().timestamp())
            url = f"https://api.openai.com/v1/organization/costs?limit=1&start_time={start_time}"
            response = await client.get(url, headers=HEADERS)
            response.raise_for_status()
            response_json = response.json()
            logger.info(f"API response: {response_json}")

        # Extract results safely
        data = response_json.get("data")
        if not data or not data[0].get("results"):
            logger.warning("No usage data found in API response.")
            return

        results = data[0]["results"]
        usage_value = results[0]["amount"]["value"]
        usage_currency = results[0]["amount"]["currency"]

        usage_diff = usage_value - last_api_value
        if usage_diff < 0:
            usage_diff = 0  # prevent negative deduction

        new_balance = max(0, last_balance - usage_diff)

        # Update DB
        await remaining_balance_collection.update_one(
            {"_id": balance_doc["_id"]},
            {
                "$set": {
                    "remaining_credits": new_balance,
                    "last_api_value": usage_value,
                    "last_start_time": data[0]["start_time"],
                    "last_end_time": data[0]["end_time"],
                    "updated_at": datetime.utcnow()
                }
            }
        )
        logger.info(f"Updated remaining balance: {new_balance} {usage_currency} (usage diff: {usage_diff})")

        # Check threshold and send alert emails if needed
        if new_balance <= THRESHOLD:
            logger.warning(f"Remaining balance {new_balance} is at or below threshold {THRESHOLD}. Sending alerts...")
            # Fetch all emails from DB
            async for doc in email_address_collection.find({}):
                to_email = doc.get("email")
                subject = "⚠️ OpenAI Credit Alert"
                body = f"Your remaining OpenAI balance is {new_balance} {usage_currency}, which is at or below the threshold of {THRESHOLD}."
                try:
                    await send_email(to_email, subject, body)
                    logger.info(f"Alert email sent to {to_email}")
                except Exception as e:
                    logger.error(f"Failed to send alert email to {to_email}: {e}")

    except httpx.HTTPError as e:
        logger.error(f"HTTP error while fetching OpenAI usage: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in check_user_credits: {e}")


async def run_monitor():
    """
    Scheduled task to check user credits periodically.
    """
    await check_user_credits()
