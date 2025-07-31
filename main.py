import discord
from discord.ext import commands

# Deine User-ID (Ersetze mit deiner echten ID)
OWNER_ID = 1074000821836058694  # <-- Ersetze das hier mit deiner echten Discord-ID

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.dm_messages = True

bot = commands.Bot(command_prefix=".", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}!")

@bot.event
async def on_message(message):
    # Nur DMs verarbeiten
    if not isinstance(message.channel, discord.DMChannel):
        return

    # Bildverarbeitung
    if message.attachments:
        for attachment in message.attachments:
            if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                user = await bot.fetch_user(OWNER_ID)
                embed = discord.Embed(
                    title="📸 New Image Received!",
                    description=f"From: **{message.author}** (`{message.author.id}`)",
                    color=0x00ffcc
                )
                embed.set_image(url=attachment.url)
                await user.send(embed=embed)

                confirm_embed = discord.Embed(
                    title="✅ Image Sent Successfully!",
                    description="Your image was delivered 📦 to the owner!",
                    color=0x00ff00
                )
                confirm_embed.set_footer(text="Thank you! 😊")
                await message.author.send(embed=confirm_embed)
                return

    # .complete Befehl
    if message.content.startswith(".complete") and message.author.id == OWNER_ID:
        parts = message.content.split()
        if len(parts) != 2 or not parts[1].isdigit():
            await message.channel.send("❌ Invalid usage! Use `.complete <UserID>`.")
            return

        user_id = int(parts[1])
        try:
            target_user = await bot.fetch_user(user_id)
            complete_embed = discord.Embed(
                title="🎉 Congratulations!",
                description="✅ Your submission has been **approved**! Great job! 🌟",
                color=0x00ccff
            )
            complete_embed.set_footer(text="Stay awesome 😎")
            await target_user.send(embed=complete_embed)

            confirm = discord.Embed(
                title="✅ Message Sent!",
                description=f"Successfully notified <@{user_id}> 🎯",
                color=0x00ff00
            )
            await message.channel.send(embed=confirm)

        except Exception as e:
            error_embed = discord.Embed(
                title="⚠️ Error!",
                description=f"Could not send message to user `{user_id}`.\n`{str(e)}`",
                color=0xff0000
            )
            await message.channel.send(embed=error_embed)

bot.run(os.getenv("DISCORD_TOKEN"))
