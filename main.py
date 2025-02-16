"""Bring! TRMNL plugin"""

import asyncio
import copy
import datetime
import os
import time
from dataclasses import dataclass, field
from typing import List

import aiohttp
from aiohttp.web_exceptions import HTTPException
from bring_api import Bring
from bring_api.exceptions import BringException
from dotenv import load_dotenv

load_dotenv()

EXCEPTION_SLEEP_INTERVAL = 60
PLUGIN_SLEEP_INTERVAL = 60 * 15  # 15 minutes


@dataclass
class BringList:
    """Represents a Bring list"""

    name: str = ""
    uuid: str = ""
    items: List[str] = field(default_factory=list)

    def __eq__(self, other):
        if isinstance(other, BringList):
            return (
                self.name == other.name
                and self.uuid == other.uuid
                and set(self.items) == set(other.items)
            )
        return False


class BringPlugin:
    """
    Class syncing Bring shopping list with TRMNL.
    The plugin currently supports only one shopping list.
    """

    def __init__(self):
        self.email = os.getenv("EMAIL")
        self.password = os.getenv("PASSWORD")
        self.webhook_url = os.getenv("WEBHOOK_URL")
        self.bring = None
        self.existing_list = None

    async def grab_items(self, bring_list):
        """Grabs the items of the list using the list's uuid"""
        item_objs = (await self.bring.get_list(bring_list.uuid)).items.purchase
        bring_list.items = [item.itemId for item in item_objs]
        print(f"Successfully fetched items at {datetime.datetime.now().isoformat()}")
        print(f"Items = {bring_list.items}")

    async def send_list_to_trmnl(self, session, bring_list):
        """Sends the list to TRMNL if it has changed"""
        if self.existing_list == bring_list:
            print("The items list hasn't changed since the last fetch.")
            print("Skipping sending updates to TRMNL.")
            return
        self.existing_list = bring_list

        try:
            await session.post(
                self.webhook_url,
                json={
                    "merge_variables": {
                        "items": self.existing_list.items,
                        "list_name": self.existing_list.name,
                    }
                },
                headers={"Content-Type": "application/json"},
                raise_for_status=True,
            )

            current_timestamp = datetime.datetime.now().isoformat()
            print(f"Items sent successfully to TRMNL at {current_timestamp}")
        except HTTPException as e:
            print(f"Exception occurred during sending items to TRMNL: {e}")

    async def run(self):
        """Start the plugin"""
        async with aiohttp.ClientSession() as session:
            self.bring = Bring(session, self.email, self.password)
            await self.bring.login()

            while True:
                new_list = None
                if self.existing_list:
                    new_list = copy.deepcopy(self.existing_list)
                else:
                    bring_api_list = (await self.bring.load_lists()).lists[0]
                    new_list = BringList(name=bring_api_list.name, uuid=bring_api_list.listUuid)

                await self.grab_items(new_list)
                await self.send_list_to_trmnl(session, new_list)
                time.sleep(PLUGIN_SLEEP_INTERVAL)


if __name__ == "__main__":
    bring_plugin = BringPlugin()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    while True:
        try:
            loop.run_until_complete(bring_plugin.run())
        except BringException as e:
            print(f"Bring exception occured: {e}")
            print(f"Sleeping for {EXCEPTION_SLEEP_INTERVAL} seconds.")
            time.sleep(EXCEPTION_SLEEP_INTERVAL)
            print("Retrying the service")
        except Exception as e:
            print(f"Unknown exception occured: {e}")
            raise
