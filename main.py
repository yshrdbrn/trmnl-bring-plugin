import aiohttp
import asyncio
import datetime
import os
import time

from dotenv import load_dotenv

from bring_api import Bring
from bring_api.exceptions import BringException

load_dotenv()

class BringPlugin:
    SLEEP_INTERVAL = 15 * 60 # 15 minutes

    def __init__(self):
        self.email = os.getenv('EMAIL')
        self.password = os.getenv('PASSWORD')
        self.webhook_url = os.getenv('WEBHOOK_URL')
        self.items = []

    async def grabItems(self):
        itemObjs = (await self.bring.get_list(self.list)).items.purchase
        items = [item.itemId for item in itemObjs]
        print(f"Items fetched: {items}")
        return items
    
    async def sendItemsToTerminal(self, session, items):
        if set (self.items) == set(items):
            print(f"The items list hasn't changed since the last fetch.")
            print(f"Skipping sending updates to TRMNL.")
            return
        self.items = items

        try:
            await session.post(
                self.webhook_url,
                json={'merge_variables': {'items': items}},
                headers={'Content-Type': 'application/json'},
                raise_for_status=True)
            
            current_timestamp = datetime.datetime.now().isoformat()
            print(f"Items sent successfully to TRMNL at {current_timestamp}")
        except Exception as e:
            print(f"Exception occurred during sending items to TRMNL: {e}")

    async def run(self):
        async with aiohttp.ClientSession() as session:
            self.bring = Bring(session, self.email, self.password)
            await self.bring.login()

            while True:
                self.list = (await self.bring.load_lists()).lists[0].listUuid
                items = await self.grabItems()
                await self.sendItemsToTerminal(session, items)
                time.sleep(self.SLEEP_INTERVAL)


if __name__ == "__main__":
    bring_plugin = BringPlugin()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while True:
        try:
            loop.run_until_complete(bring_plugin.run())
        except BringException as e:
            print(f"Bring exception occured: {e}")
            print(f"Retrying the service")
        except Exception as e:
            print(f"Unknowne exception occured: {e}")
            raise