import json
from typing import Dict
import os

class ServerData:
    def __init__(self, filename="server_data.json"):
        self.filename = filename
        self.data = self._load_data()

    def _load_data(self) -> Dict:
        if os.path.exists(self.filename):
            with open(self.filename, 'r') as f:
                return json.load(f)
        return {}

    def save_data(self):
        with open(self.filename, 'w') as f:
            json.dump(self.data, f, indent=4)

    def add_server(self, guild_id: int, category_id: int, channel_id: int):
        self.data[str(guild_id)] = {
            "category_id": category_id,
            "channel_id": channel_id,
            "settings_channel_id": None,
            "support_enabled": True,
            "max_tickets": 50,
            "active_tickets": {}
        }
        self.save_data()

    def update_settings(self, guild_id: int, settings_channel_id: int = None, support_enabled: bool = None, max_tickets: int = None):
        guild_id = str(guild_id)
        if guild_id in self.data:
            if settings_channel_id is not None:
                self.data[guild_id]["settings_channel_id"] = settings_channel_id
            if support_enabled is not None:
                self.data[guild_id]["support_enabled"] = support_enabled
            if max_tickets is not None:
                self.data[guild_id]["max_tickets"] = max_tickets
            self.save_data()

    def add_ticket(self, guild_id: int, ticket_channel_id: int, user_id: int):
        guild_id = str(guild_id)
        if guild_id in self.data:
            self.data[guild_id]["active_tickets"][str(ticket_channel_id)] = {
                "user_id": user_id,
                "claimed_by": None
            }
            self.save_data()

    def remove_ticket(self, guild_id: int, ticket_channel_id: int):
        guild_id = str(guild_id)
        if guild_id in self.data:
            self.data[guild_id]["active_tickets"].pop(str(ticket_channel_id), None)
            self.save_data()

    def update_ticket_claim(self, guild_id: int, ticket_channel_id: int, admin_id: int):
        guild_id = str(guild_id)
        if guild_id in self.data:
            self.data[guild_id]["active_tickets"][str(ticket_channel_id)]["claimed_by"] = admin_id
            self.save_data()

    def get_server_data(self, guild_id: int) -> Dict:
        return self.data.get(str(guild_id), None)
