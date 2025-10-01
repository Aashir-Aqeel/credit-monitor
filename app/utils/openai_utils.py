import requests
from datetime import datetime, timedelta

def get_openai_usage(api_key: str, days: int = 1):
    """
    Fetch OpenAI API usage for the last `days` days.
    Default: today's usage (days=1).
    """
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days - 1)

    url = f"https://api.openai.com/v1/dashboard/billing/usage?start_date={start_date}&end_date={end_date}"
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        total_used = data.get("total_usage", 0) / 100.0  # API returns in cents
        return total_used
    else:
        raise Exception(f"Failed to fetch usage: {response.status_code} - {response.text}")


def get_openai_subscription(api_key: str):
    """
    Fetch OpenAI subscription info (hard limit & expiry).
    """
    url = "https://api.openai.com/v1/dashboard/billing/subscription"
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        hard_limit = data.get("hard_limit_usd", 0.0)
        return hard_limit
    else:
        raise Exception(f"Failed to fetch subscription: {response.status_code} - {response.text}")


def get_openai_report(api_key: str):
    """
    Build a usage report with today's, monthly usage, and remaining balance.
    """
    today_usage = get_openai_usage(api_key, days=1)

    # Monthly usage: from 1st of current month to today
    start_of_month = datetime.utcnow().replace(day=1).date()
    end_date = datetime.utcnow().date()
    url = f"https://api.openai.com/v1/dashboard/billing/usage?start_date={start_of_month}&end_date={end_date}"
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(url, headers=headers)

    monthly_usage = 0.0
    if response.status_code == 200:
        data = response.json()
        monthly_usage = data.get("total_usage", 0) / 100.0

    # Subscription / hard limit
    total_limit = get_openai_subscription(api_key)
    remaining_balance = total_limit - monthly_usage

    return {
        "today_usage": today_usage,
        "monthly_usage": monthly_usage,
        "total_limit": total_limit,
        "remaining_balance": remaining_balance
    }
