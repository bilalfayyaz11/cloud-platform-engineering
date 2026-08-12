import json
from datetime import datetime, timezone


def lambda_handler(event: dict, context) -> dict:
    name = event.get("name", "World")

    timestamp = datetime.now(timezone.utc).isoformat()

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": f"Welcome, {name}! Your Lambda function was updated successfully.",
            "timestamp": timestamp,
            "version": 2
        })
    }
