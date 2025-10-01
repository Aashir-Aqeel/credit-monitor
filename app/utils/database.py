from motor.motor_asyncio import AsyncIOMotorClient
import os

MONGO_URI = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME", "credit_monitor")

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

# ✅ Define the collections properly
remaining_balance_collection = db["remaining_balance"]
email_address_collection = db["email_address"]

print("DEBUG - database.py loaded successfully")
print("DEBUG - collections:", remaining_balance_collection.name, email_address_collection.name)
