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

REG_RESULTS_CHANNEL_ID = 1375786132775899186
REG_QUESTIONS = [
    "What is your full name?",
    "What is your email address?",
    "What is your phone number?",
    "Do you have any dietary restrictions?",
    "Any other comments?"
]
user_reg_sessions = {}

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
            await interaction.user.send("Let's get you registered! Please answer the following questions one by one.")
            user_reg_sessions[interaction.user.id] = {
                'step': 0,
                'answers': [],
                'event_name': interaction.message.embeds[0].title if interaction.message.embeds else None
            }
            await interaction.user.send(REG_QUESTIONS[0])
            await interaction.response.send_message("Check your DMs to complete registration!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Failed to DM you: {e}", ephemeral=True)

class ApproveView(ui.View):
    def __init__(self, announcement, reg_channel_id):
        super().__init__(timeout=600)
        self.announcement = announcement
        self.reg_channel_id = reg_channel_id
        self.approved = False

    @ui.button(label="Approve", style=discord.ButtonStyle.success, custom_id="approve_button")
    async def approve_button(self, interaction: Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("You do not have permission to approve.", ephemeral=True)
            return
        if self.approved:
            await interaction.response.send_message("Already approved.", ephemeral=True)
            return
        self.approved = True
        reg_channel = interaction.client.get_channel(self.reg_channel_id)
        if not reg_channel:
            await interaction.response.send_message("Registration channel not found.", ephemeral=True)
            return
        # Remove/disable previous registration buttons
        async for msg in reg_channel.history(limit=50):
            if msg.author == interaction.client.user and msg.components:
                try:
                    await msg.edit(view=RegisterView(disabled=True))
                except Exception:
                    pass
        await reg_channel.send(self.announcement, view=RegisterView())
        # Extract event name (title) from announcement
        event_name = None
        for line in self.announcement.split("\n"):
            if line.startswith("**") and line.endswith("**"):
                event_name = line.strip("*")
                break
        results_channel = interaction.client.get_channel(REG_RESULTS_CHANNEL_ID)
        if results_channel and event_name:
            await results_channel.send(f"Registrations for {event_name}")
        await interaction.response.send_message(f"Registration announcement posted in <#{self.reg_channel_id}>.", ephemeral=True)
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(content=f"✅ Approved and posted to <#{self.reg_channel_id}>.", view=self)

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

    # DM registration flow
    if isinstance(message.channel, discord.DMChannel):
        session = user_reg_sessions.get(message.author.id)
        if session:
            step = session['step']
            answers = session['answers']
            if step < len(REG_QUESTIONS):
                answers.append(message.content)
                session['step'] += 1
                if session['step'] < len(REG_QUESTIONS):
                    await message.author.send(REG_QUESTIONS[session['step']])
                else:
                    # Registration complete
                    reg_channel = bot.get_channel(REG_RESULTS_CHANNEL_ID)
                    if reg_channel:
                        result = f"Registration from {message.author.mention} (ID: {message.author.id}):\n"
                        for i, q in enumerate(REG_QUESTIONS):
                            result += f"**{q}**\n{answers[i]}\n"
                        await reg_channel.send(result)
                    await message.author.send("Thank you! Your registration has been submitted.")
                    del user_reg_sessions[message.author.id]
            return

    # Only echo in guild text channels
    if isinstance(message.channel, discord.TextChannel):
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

    # Send preview with Approve button in invoking channel
    await interaction.channel.send(
        f"**Registration Announcement Preview:**\n\n{announcement}",
        view=ApproveView(announcement, REG_CHANNEL_ID)
    )
    await interaction.response.send_message(
        f"Preview sent with Approve button. Only a mod can approve.", ephemeral=True
    )

# Error handler for slash command permissions
@announce_registration.error
async def announce_registration_error(interaction: Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Error: {error}", ephemeral=True)

if __name__ == '__main__':
    bot.run(TOKEN)
