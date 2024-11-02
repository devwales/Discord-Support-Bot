import discord
from discord.ext import commands
from discord import app_commands
import random
import string
import asyncio
from data_manager import ServerData

class TicketBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix=';', intents=intents)
        self.server_data = ServerData()
        
    async def setup_hook(self):
        await self.tree.sync()

bot = TicketBot()

class SupportSettingsView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        server_data = bot.server_data.get_server_data(guild_id)
        self.support_enabled = server_data.get("support_enabled", True)
        self.max_tickets = server_data.get("max_tickets", 50)
        self._update_button_states()

    def _update_button_states(self):
        toggle_button = [x for x in self.children if x.custom_id == "toggle_support"][0]
        toggle_button.label = f"Support Status: {'Enabled' if self.support_enabled else 'Disabled'}"
        toggle_button.style = discord.ButtonStyle.green if self.support_enabled else discord.ButtonStyle.red

    @discord.ui.button(label="Support Status: Enabled", style=discord.ButtonStyle.green, custom_id="toggle_support")
    async def toggle_support(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return
        
        self.support_enabled = not self.support_enabled
        bot.server_data.update_settings(self.guild_id, support_enabled=self.support_enabled)
        self._update_button_states()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Set Max Tickets", style=discord.ButtonStyle.blurple, custom_id="max_tickets")
    async def set_max_tickets(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return

        await interaction.response.send_message("How many tickets maximum? (1-50)", ephemeral=True)
        
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel
        
        try:
            msg = await interaction.client.wait_for('message', timeout=30.0, check=check)
            try:
                new_max = min(int(msg.content), 50)
                self.max_tickets = max(1, new_max)
                bot.server_data.update_settings(self.guild_id, max_tickets=self.max_tickets)
                await msg.delete()
                await interaction.followup.send(f"Max tickets set to {self.max_tickets}", ephemeral=True)
            except ValueError:
                self.max_tickets = 50
                bot.server_data.update_settings(self.guild_id, max_tickets=self.max_tickets)
                await interaction.followup.send("Invalid input. Max tickets set to 50", ephemeral=True)
        except asyncio.TimeoutError:
            self.max_tickets = 50
            bot.server_data.update_settings(self.guild_id, max_tickets=self.max_tickets)
            await interaction.followup.send("Timeout. Max tickets set to 50", ephemeral=True)

    @discord.ui.button(label="Delete All Tickets", style=discord.ButtonStyle.red, custom_id="delete_all")
    async def delete_all_tickets(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return
            
        confirm_view = ConfirmView()
        await interaction.response.send_message("Are you sure you want to delete ALL tickets?", view=confirm_view, ephemeral=True)
        
        await confirm_view.wait()
        if confirm_view.value:
            server_data = bot.server_data.get_server_data(self.guild_id)
            if server_data and "active_tickets" in server_data:
                for ticket_id in list(server_data["active_tickets"].keys()):
                    channel = interaction.guild.get_channel(int(ticket_id))
                    if channel:
                        await channel.delete()
                    bot.server_data.remove_ticket(self.guild_id, int(ticket_id))
                await interaction.followup.send("All tickets have been deleted!", ephemeral=True)

class TicketManageView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.claimed_by = None
    
    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.primary, custom_id="claim_ticket")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        staff_role = discord.utils.get(interaction.guild.roles, name="Support Staff")
        if not staff_role in interaction.user.roles:
            await interaction.response.send_message("Only Support Staff can claim tickets!", ephemeral=True)
            return            
        self.claimed_by = interaction.user
        button.disabled = True
        button.label = f"Claimed by {interaction.user.name}"
        
        embed = discord.Embed(
            title="Ticket Claimed",
            description=f"This ticket has been claimed by {interaction.user.mention}",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(embed=embed)
    
    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator and interaction.user != interaction.channel.name.split('-')[1]:
            await interaction.response.send_message("You cannot close this ticket!", ephemeral=True)
            return
        
        bot.server_data.remove_ticket(interaction.guild.id, interaction.channel.id)
        
        await interaction.response.send_message("Closing ticket in 5 seconds...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

class ConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)
        self.value = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()
        await interaction.response.defer()

@bot.hybrid_command(name="setupsupport", description="Set up the support ticket system")
@commands.has_permissions(administrator=True)
async def setupsupport(ctx):
    # Get or create Support Staff role
    staff_role = discord.utils.get(ctx.guild.roles, name="Support Staff")
    if not staff_role:
        staff_role = await ctx.guild.create_role(name="Support Staff", permissions=discord.Permissions.all())
        await ctx.send("Created Support Staff role!")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    await ctx.send("What would you like to name the support channel? (Type your response or wait 30 seconds for default 'support')")
    
    try:
        msg = await bot.wait_for('message', timeout=30.0, check=check)
        channel_name = msg.content.lower().replace(' ', '-')
        channel_name = ''.join(c for c in channel_name if c.isalnum() or c == '-')
        channel_name = channel_name[:100]
        if not channel_name:
            channel_name = 'support'
    except asyncio.TimeoutError:
        channel_name = 'support'

    # Format the channel name with the specified prefix
    formatted_channel_name = f"〔💚〕{channel_name}"

    settings_overwrites = {
        ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        ctx.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        staff_role: discord.PermissionOverwrite(view_channel=True, send_messages=True)
    }

    # Check if support system exists
    existing_data = bot.server_data.get_server_data(ctx.guild.id)
    if existing_data:
        view = ConfirmView()
        msg = await ctx.send("A support system is already set up! Would you like to delete it and create a new one?", view=view)
        
        await view.wait()
        if view.value is None:
            await msg.edit(content="Setup timed out! No changes were made.", view=None)
            return
        if not view.value:
            await msg.edit(content="Setup cancelled! Existing support system remains unchanged.", view=None)
            return
            
        # Delete existing channels
        try:
            category = ctx.guild.get_channel(existing_data["category_id"])
            if category:
                for channel in category.channels:
                    await channel.delete()
                await category.delete()
        except:
            pass

    overwrites = {
        ctx.guild.default_role: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=False,
            add_reactions=False
        ),
        ctx.guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            add_reactions=True
        )
    }
    
    # Create the category with the specified name
    category = await ctx.guild.create_category("┗⎯⎯⎯⎯⎯⎯|💚|SUPPORT|💚|⎯⎯⎯⎯⎯⎯┑")
    support_channel = await ctx.guild.create_text_channel(
        name=formatted_channel_name, 
        category=category,
        overwrites=overwrites
    )
    
    bot.server_data.add_server(ctx.guild.id, category.id, support_channel.id)
    
    embed = discord.Embed(
        title="Support Tickets",
        description="Please choose a subject from the dropdown menu before you are able to click 'Create Ticket'.",
        color=discord.Color.blue()
    )
    
    await support_channel.send(embed=embed, view=TicketView())

    # Create settings channel with proper staff role permissions
    settings_channel = await ctx.guild.create_text_channel(
        "support-settings",
        category=category,
        overwrites=settings_overwrites
    )

    settings_embed = discord.Embed(
        title="Support Settings",
        description="Control panel for support ticket system",
        color=discord.Color.blue()
    )
    
    await settings_channel.send(embed=settings_embed, view=SupportSettingsView(ctx.guild.id))

    await ctx.send(f"Support system has been set up in {support_channel.mention}!")

# Ensure there are no other registrations of the same command elsewhere in your code    @bot.event
    async def on_ready():
        print(f'Bot is ready! Logged in as {bot.user.name}')
        bot.add_view(TicketView())
        bot.add_view(TicketManageView())
@bot.event
async def on_message(message):
    # Process commands first
    await bot.process_commands(message)
    
    # Only check guild messages
    if message.guild and message.channel:
        server_data = bot.server_data.get_server_data(message.guild.id)
        if server_data and str(message.channel.id) == str(server_data["channel_id"]):
            if message.author != bot.user:
                await message.delete()

class SupportCategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="TikTok Live Support", description="Get help with TikTok Live issues"),
            discord.SelectOption(label="Discord Support", description="Get help with Discord related issues"),
            discord.SelectOption(label="Minecraft Support", description="Get help with Minecraft related issues"),
            discord.SelectOption(label="Other Support", description="Get help with other issues")
        ]
        super().__init__(placeholder="Select support category", options=options, custom_id="category_select")

    async def callback(self, interaction: discord.Interaction):
        create_ticket_button = [x for x in self.view.children if x.custom_id == "create_ticket"][0]
        create_ticket_button.disabled = False
        self.view.selected_category = self.values[0]
        
        embed = discord.Embed(
            title="Support Tickets",
            description="Please click 'Create Ticket' below to start your support request.",
            color=discord.Color.blue()
        )
        embed.add_field(name="Selected Category", value=self.values[0], inline=False)
        
        await interaction.response.edit_message(embed=embed, view=self.view)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.selected_category = None
        select_menu = SupportCategorySelect()
        self.add_item(select_menu)

    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.green, custom_id="create_ticket", disabled=True)
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        server_data = bot.server_data.get_server_data(interaction.guild.id)
        
        if not server_data.get("support_enabled", True):
            await interaction.response.send_message("Support system is currently disabled.", ephemeral=True)
            return
            
        current_tickets = len(server_data.get("active_tickets", {}))
        max_tickets = server_data.get("max_tickets", 50)
        
        if current_tickets >= max_tickets:
            await interaction.response.send_message(f"Maximum ticket limit ({max_tickets}) reached. Please try again later.", ephemeral=True)
            return

        ticket_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        category_prefix = self.selected_category.lower().replace(" ", "-")
        channel_name = f"ticket-{category_prefix}-{interaction.user.name}-{ticket_id}"
        
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        
        staff_role = discord.utils.get(interaction.guild.roles, name="Support Staff")
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
        ticket_channel = await interaction.guild.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            category=interaction.channel.category
        )
        
        bot.server_data.add_ticket(interaction.guild.id, ticket_channel.id, interaction.user.id)
        
        ticket_manage = TicketManageView()
        embed = discord.Embed(
            title=f"Ticket #{ticket_id}",
            description=f"Created by {interaction.user.mention}\nWait for a staff member to claim your ticket.",
            color=discord.Color.blue()
        )
        
        await ticket_channel.send(embed=embed, view=ticket_manage)
        await interaction.response.send_message(f"Created ticket channel: {ticket_channel.mention}", ephemeral=True)