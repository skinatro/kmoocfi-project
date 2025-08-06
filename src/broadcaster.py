"""
Simple NATS to Discord Broadcaster
"""
import os
import asyncio
from discord_webhook import DiscordWebhook
from nats import connect

NATS_URL = os.environ.get("NATS_URL", "nats://nats-service:4222")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def push_to_discord(message: str):
    """Sends message to discord"""
    webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, rate_limit_retry=True, content=message)
    webhook.execute()

async def message_handler(msg):
    """Get the message and send it to discord"""
    subject = msg.subject
    data = msg.data.decode()
    push_to_discord(f"Received on [{subject}]: {data}")

async def main():
    """Listen to subject db-updates and call message_handler"""
    nc = await connect(NATS_URL)
    await nc.subscribe("db-updates", cb=message_handler)
    
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
