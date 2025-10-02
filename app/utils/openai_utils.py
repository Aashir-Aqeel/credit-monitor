import os
import aiohttp
import logging

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
print(f"OPENAI_API_KEY: {OPENAI_API_KEY}")
OPENAI_BASE = "https://api.openai.com/v1"

async def get_openai_usage():
    """
    Fetch usage from OpenAI organization/costs API.
    Returns the full response dict (not a float).
    """
    url = "https://api.openai.com/v1/organization/costs?start_time=1758844800&end_time=1759104000"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.warning(f"OpenAI usage request failed: {resp.status} - {text}")
                    return {}

                data = await resp.json()
                logger.info(f"OpenAI usage data: {data}")

                return data  # Return the full response

    except Exception as e:
        logger.exception(f"Exception while fetching OpenAI usage: {e}")
        return {}
