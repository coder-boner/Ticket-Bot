#MADE BY Coder-Boner (https://github.com/coder-boner/)
#Repo (https://github.com/coder-boner/Ticket-Bot)


import discord
from discord.ext import commands
from discord.utils import get
import json
from datetime import datetime
from pytz import timezone
import os
import asyncio

# Bot setup
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
intents.guild_messages = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Configuration
TICKET_CATEGORY_ID = CATEGORY_ID  # Replace with the ID of the "Open Tickets" category
ARCHIVE_CATEGORY_ID = CATEGORY_ID  # Replace with the ID of the "Archived Tickets" category
SUPPORT_ROLE_ID = ROLE_ID  # Replace with the support role ID
TICKET_NUMBER_FILE = "ticket_number.json"  # File to persist ticket number
CHAT_LOGS_PATH = "chat_logs/"  # Directory to store chat logs

#DANGER THIS IS FOR THE MASS CHANNEL DELETE FOR CLOSED TICKETS
DEL_CATEGORY_ID = CATEGORY_ID  # ID of the category
AUTHORIZED_USER_ID = USER_ID  # ID of the authorized user


# Ensure chat logs directory exists
os.makedirs(CHAT_LOGS_PATH, exist_ok=True)

# Colors for ticket status
ticket_status_colors = {
    "unclaimed": "🟡",  # Yellow circle
    "claimed": "🟢",   # Green circle
    "closed": "🔴"     # Red circle
}

# Load or initialize ticket number
def load_ticket_number():
    try:
        with open(TICKET_NUMBER_FILE, "r") as f:
            return json.load(f).get("ticket_number", 1)
    except FileNotFoundError:
        return 1

def save_ticket_number(number):
    with open(TICKET_NUMBER_FILE, "w") as f:
        json.dump({"ticket_number": number}, f)

TICKET_NUMBER = load_ticket_number()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}!")

    # Count active tickets
    ticket_category = bot.get_channel(TICKET_CATEGORY_ID)
    if ticket_category:
        active_tickets = len([channel for channel in ticket_category.channels if channel.name.startswith(ticket_status_colors['unclaimed']) or channel.name.startswith(ticket_status_colors['claimed'])])
    else:
        active_tickets = 0

    # Count ticket logs
    ticket_logs_path = CHAT_LOGS_PATH
    if os.path.exists(ticket_logs_path):
        ticket_logs = len([file for file in os.listdir(ticket_logs_path) if file.endswith('.txt')])
    else:
        ticket_logs = 0

    # Update bot presence
    total_tickets = active_tickets + ticket_logs
    await bot.change_presence(activity=discord.Game(name=f"Managing {total_tickets} tickets"))

    # Ensure this runs on every restart
    bot.loop.create_task(on_ready())

# Dropdown menu class
class TicketTypeDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="SCP:SL", description="Support for SCP: Secret Laboratory."),
            discord.SelectOption(label="Discord", description="Support for Discord-related issues."),
            discord.SelectOption(label="Other", description="Support for other issues.")
        ]
        super().__init__(placeholder="Choose a ticket type...", options=options)

    async def callback(self, interaction: discord.Interaction):
        # Your existing code here
        await interaction.response.defer() # Defer the interaction to avoid timeout

    async def callback(self, interaction: discord.Interaction):
        global TICKET_NUMBER

        ticket_type = self.values[0]  # Get the selected ticket type
        ticket_name = f"{ticket_status_colors['unclaimed']}-{ticket_type}-{TICKET_NUMBER}"
        ticket_creator = interaction.user
        TICKET_NUMBER += 1  # Increment the ticket number
        save_ticket_number(TICKET_NUMBER)

        # Get the ticket category
        category = interaction.guild.get_channel(TICKET_CATEGORY_ID)
        if not category:
            await interaction.response.send_message("Ticket category not found!", ephemeral=True)
            return

        # Create the ticket channel
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.get_role(SUPPORT_ROLE_ID): discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        ticket_channel = await category.create_text_channel(name=ticket_name, overwrites=overwrites)

        # Send a message in the ticket channel
        creation_time = datetime.now(timezone('UTC')).astimezone()
        message = f"{ticket_creator.mention} has made a ticket, {interaction.guild.get_role(SUPPORT_ROLE_ID).mention} will be with you soon. Please be patient."
        await ticket_channel.send(message)

        # Send the creation details to the ticket creator's DMs
        try:
            await ticket_creator.send(f"Your ticket has been created: {ticket_channel.mention}")
        except discord.Forbidden:
            await interaction.response.send_message(f"Your ticket has been created: {ticket_channel.mention}. However, I couldn't send you a DM with the details.", ephemeral=True)

        await interaction.response.send_message(f"Your ticket has been created: {ticket_channel.mention}", ephemeral=True)

# View class to hold the dropdown
class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Set timeout to None to disable it
        self.add_item(TicketTypeDropdown())


# Custom check to ensure only the authorized user can use the command
def is_authorized_user():
    def predicate(ctx):
        return ctx.author.id == AUTHORIZED_USER_ID
    return commands.check(predicate)

@bot.command()
@is_authorized_user()
async def ticket(ctx):
    """Command to start the ticket creation process."""
    view = TicketView()
    try:
        await ctx.send("Select a ticket type to create a new ticket:", view=view)
    except discord.Forbidden:
        await ctx.send("I do not have permission to send messages in this channel.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred: {e.text}")


@bot.command()
async def claim(ctx):
    """Command to claim a ticket."""
    if ctx.channel.category_id != TICKET_CATEGORY_ID:
        await ctx.send("This command can only be used in ticket channels.")
        return

    # Check if the user has the support role
    support_role = get(ctx.guild.roles, id=SUPPORT_ROLE_ID)
    if support_role not in ctx.author.roles:
        await ctx.send("You don't have permission to claim this ticket.")
        return

    # Change the ticket status to claimed
    new_name = ctx.channel.name.replace(ticket_status_colors['unclaimed'], ticket_status_colors['claimed'])
    await ctx.channel.edit(name=new_name)
    await ctx.send(f"This ticket has been claimed by {ctx.author.mention}.")

@bot.command()
async def close(ctx, *, reason: str = None):
    """Command to close a ticket."""
    if ctx.channel.category_id != TICKET_CATEGORY_ID:
        await ctx.send("This command can only be used in ticket channels.")
        return

    # Check if the user has the support role
    support_role = get(ctx.guild.roles, id=SUPPORT_ROLE_ID)
    if support_role not in ctx.author.roles:
        await ctx.send("You don't have permission to close this ticket.")
        return

    # Ensure the reason is not empty
    if reason is None or reason.strip() == "":
        await ctx.send("Reason cannot be empty. Please provide a reason to close the ticket.")
        return

    # Change the ticket status to closed
    new_name = ctx.channel.name
    if ticket_status_colors['claimed'] in new_name:
        new_name = new_name.replace(ticket_status_colors['claimed'], ticket_status_colors['closed'])
    elif ticket_status_colors['unclaimed'] in new_name:
        new_name = new_name.replace(ticket_status_colors['unclaimed'], ticket_status_colors['closed'])

    await ctx.channel.edit(name=new_name)

    # Archive the ticket
    archive_category = ctx.guild.get_channel(ARCHIVE_CATEGORY_ID)
    if not archive_category:
        await ctx.send("Archive category not found!")
        return
    await ctx.channel.edit(category=archive_category)

    # Log and send chat history
    messages = [msg async for msg in ctx.channel.history(limit=None, oldest_first=True)]
    chat_log_path = f"{CHAT_LOGS_PATH}ticket_{new_name}.txt"
    with open(chat_log_path, "w", encoding="utf-8") as log_file:
        for msg in messages:
            log_file.write(f"[{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {msg.author}: {msg.content}\n")

    with open(chat_log_path, "rb") as log_file:
        await ctx.author.send("Here is the chat log for your closed ticket:", file=discord.File(log_file, chat_log_path))

    # Send closure details
    closure_time = datetime.now(timezone('UTC')).astimezone()
    embed = discord.Embed(title="Ticket Closed", color=discord.Color.red())
    embed.add_field(name="Closed By", value=ctx.author.mention, inline=False)
    embed.add_field(name="Closure Time", value=closure_time.strftime("%A, %B %d, %Y %I:%M %p %Z"), inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)

    # Find the ticket creator
    messages = [msg async for msg in ctx.channel.history(limit=100, oldest_first=True)]
    for msg in messages:
        if msg.embeds and msg.embeds[0].title == "Ticket Created":
            ticket_creator = msg.embeds[0].fields[0].value.replace("!", "")
            break
    else:
        ticket_creator = None

    if ticket_creator:
        try:
            ticket_creator_user = await bot.fetch_user(int(ticket_creator.strip("<@>")))
            await ticket_creator_user.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            await ctx.send("Could not send the closure details to the ticket creator's DMs.", delete_after=10)

    await ctx.channel.send(embed=embed)

@bot.command()
async def delete_category_channels(ctx):
    # Check if the command is used by the authorized user
    if ctx.author.id != AUTHORIZED_USER_ID:
        await ctx.send("You do not have permission to use this command.")
        return

    # Specify the category ID
    category_id = DEL_CATEGORY_ID  # Replace with the ID of the category you want to delete channels from

    # Get the category
    category = ctx.guild.get_channel(category_id)
    if not category or not isinstance(category, discord.CategoryChannel):
        await ctx.send("Category not found or is not a category channel.")
        return

    # Delete all channels in the category
    for channel in category.channels:
        try:
            await channel.delete()
            await ctx.send(f"Deleted channel: {channel.name}")
        except discord.Forbidden:
            await ctx.send(f"Failed to delete channel: {channel.name} due to lack of permissions.")
        except discord.HTTPException as e:
            await ctx.send(f"Failed to delete channel: {channel.name} - {e.text}")

    await ctx.send("All channels in the category have been deleted.")

# Run the bot
bot.run("TOKEN")