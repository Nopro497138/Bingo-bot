import discord
from discord.ext import commands
import os

# Deine Discord User-ID
OWNER_ID = 1074000821836058694  # <--- ERSETZEN!

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

    # Nur der Owner darf Commands senden
    if message.author.id != OWNER_ID:
        return

    parts = message.content.strip().split()
    if len(parts) != 2 or not parts[1].isdigit():
        if message.content.startswith(".complete") or message.content.startswith(".fail"):
            await message.channel.send("❌ Invalid usage! Use `.complete <UserID>` or `.fail <UserID>`.")
        return

    command = parts[0]
    user_id = int(parts[1])

    try:
        target_user = await bot.fetch_user(user_id)

        if command == ".complete":
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

        elif command == ".fail":
            fail_embed = discord.Embed(
                title="❌ Submission Failed",
                description="😕 Your picture did not meet the requirements.\nPlease try again later. 📷",
                color=0xff0000
            )
            fail_embed.set_footer(text="Better luck next time 🍀")
            await target_user.send(embed=fail_embed)

            confirm = discord.Embed(
                title="📪 Message Sent!",
                description=f"Failure message sent to <@{user_id}> 🚫",
                color=0xff9900
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
