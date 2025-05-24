import discord
from discord.ext import commands
from discord import ui, Interaction
from discord import app_commands
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

intents = discord.Intents.default()
intents.message_content = True  # Required to read message content
intents.members = True  # Needed for DM functionality

bot = commands.Bot(command_prefix='!', intents=intents)

# Channel where registration announcements will be posted
REG_CHANNEL_ID = 1375774964350976060

# Store the last registration message IDs for cleanup
last_reg_message_ids = []

class RegisterView(ui.View):
    def __init__(self, disabled=False):
        super().__init__(timeout=None)
        self.disabled = disabled

    @ui.button(label="Register", style=discord.ButtonStyle.primary, custom_id="register_button")
    async def register_button(self, interaction: Interaction, button: ui.Button):
        if self.disabled:
            await interaction.response.send_message("Registration is closed.", ephemeral=True)
            return
        try:
            await interaction.user.send("hello there bubba")
            await interaction.response.send_message("Check your DMs!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Failed to DM you: {e}", ephemeral=True)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} slash commands.')
    except Exception as e:
        print(f'Failed to sync commands: {e}')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return  # Ignore messages sent by the bot itself
    await message.channel.send(message.content)
    # Allow commands to work
    await bot.process_commands(message)

# Slash command for mods to announce registration
@bot.tree.command(name="announce_registration", description="Announce a new registration event (mod only)")
@app_commands.checks.has_permissions(manage_messages=True)
@app_commands.describe(
    title="Event title",
    subtitle="Event subtitle",
    location="Event location",
    info="Extra info",
    link="Link for event",
    description="Full event description"
)
async def announce_registration(
    interaction: Interaction,
    title: str = None,
    subtitle: str = None,
    location: str = None,
    info: str = None,
    link: str = None,
    description: str = None
):
    channel = bot.get_channel(REG_CHANNEL_ID)
    if not channel:
        await interaction.response.send_message(f"Channel with ID {REG_CHANNEL_ID} not found.", ephemeral=True)
        return

    # Remove/disable previous registration buttons
    async for msg in channel.history(limit=50):
        if msg.author == bot.user and msg.components:
            try:
                await msg.edit(view=RegisterView(disabled=True))
            except Exception:
                pass

    # Build the announcement message
    lines = []
    if title:
        lines.append(f"**{title}**")
    if subtitle:
        lines.append(f"*{subtitle}*")
    if location:
        lines.append(f"**Location:** {location}")
    if info:
        lines.append(f"**Info:** {info}")
    if link:
        lines.append(f"**Link:** {link}")
    if description:
        lines.append(f"{description}")
    lines.append("\nClick the button below to register:")
    announcement = "\n".join(lines)

    # Post new announcement
    reg_msg = await channel.send(announcement, view=RegisterView())
    await interaction.response.send_message(f"New registration announced in <#{REG_CHANNEL_ID}>.", ephemeral=True)

# Error handler for slash command permissions
@announce_registration.error
async def announce_registration_error(interaction: Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Error: {error}", ephemeral=True)

if __name__ == '__main__':
    bot.run(TOKEN)
