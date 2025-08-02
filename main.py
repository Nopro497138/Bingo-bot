import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
import os
import json
from pathlib import Path

OWNER_ID = 1074000821836058694
CHANNEL_ID = 1400939723039707217
DATA_FILE = "bot_state.json"

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.dm_messages = True

bot = commands.Bot(command_prefix=".", intents=intents)

# In-Memory Bingo Cache
bingo_state = {}

# Einmalige Startmeldung
def load_state():
    if not os.path.exists(DATA_FILE):
        return {"sent_commands": False}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_state(state):
    with open(DATA_FILE, "w") as f:
        json.dump(state, f)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}!")
    state = load_state()
    if not state.get("sent_commands", False):
        owner = await bot.fetch_user(OWNER_ID)
        embed = discord.Embed(
            title="🤖 Bot Commands",
            description=(
                "**Here are the available commands:**\n\n"
                "📩 `.complete <UserID>` – Approve a submission\n"
                "📤 `.fail <UserID>` – Reject a submission\n"
                "🎯 `.bingo <position> <text>` – Create a bingo sheet with custom text\n"
                "📡 `.bingocomplete` – Send the last bingo sheet to the server"
            ),
            color=0x7289da
        )
        embed.set_footer(text="Commands only available for bot owner 👑")
        await owner.send(embed=embed)

        state["sent_commands"] = True
        save_state(state)

@bot.event
async def on_message(message):
    if not isinstance(message.channel, discord.DMChannel):
        return

    if message.author.id != OWNER_ID:
        return

    # Bildweiterleitung
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

    content = message.content.strip()

    if content.startswith(".complete") or content.startswith(".fail"):
        parts = content.split()
        if len(parts) != 2 or not parts[1].isdigit():
            await message.channel.send("❌ Invalid usage! Use `.complete <UserID>` or `.fail <UserID>`.")
            return

        user_id = int(parts[1])
        try:
            target_user = await bot.fetch_user(user_id)

            if content.startswith(".complete"):
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

            elif content.startswith(".fail"):
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

    elif content.startswith(".bingo"):
        parts = content.split(maxsplit=2)
        if len(parts) < 3:
            await message.channel.send("❌ Usage: `.bingo <position> <text>`")
            return

        position = parts[1].lower()
        custom_text = parts[2][:15]  # Max 15 chars
        pos_map = {
            "topleft": (0, 0), "top": (0, 1), "topright": (0, 2),
            "left": (1, 0), "center": (1, 1), "right": (1, 2),
            "bottomleft": (2, 0), "bottom": (2, 1), "bottomright": (2, 2),
        }

        if position not in pos_map:
            await message.channel.send("❌ Invalid position! Try: topleft, top, center, etc.")
            return

        row, col = pos_map[position]
        sheet = [["" for _ in range(3)] for _ in range(3)]
        sheet[1][1] = "🎁"  # Free spot
        sheet[row][col] = custom_text

        # Save for .bingocomplete
        bingo_state["sheet"] = sheet
        bingo_state["author"] = message.author.name
        bingo_state["path"] = f"/tmp/bingo_{message.author.id}.png"

        # Generate image
        cell_size = 150
        padding = 10
        img_size = 3 * cell_size + 2 * padding
        img = Image.new("RGB", (img_size, img_size), color=(30, 30, 30))
        draw = ImageDraw.Draw(img)

        font_path = Path("fonts/DejaVuSans.ttf")

        for r in range(3):
            for c in range(3):
                x = c * cell_size + padding
                y = r * cell_size + padding
                draw.rectangle([x, y, x + cell_size, y + cell_size], outline="white", width=3)
                text = sheet[r][c]
                if text:
                    font_size = 40
                    while font_size > 10:
                        try:
                            font = ImageFont.truetype(str(font_path), font_size)
                        except:
                            font = ImageFont.load_default()
                        text_width, text_height = draw.textsize(text, font=font)
                        if text_width <= cell_size - 20:
                            break
                        font_size -= 2

                    text_x = x + (cell_size - text_width) / 2
                    text_y = y + (cell_size - text_height) / 2
                    draw.text((text_x, text_y), text, font=font, fill="black")

        path = bingo_state["path"]
        img.save(path)

        file = discord.File(path, filename="bingo.png")
        embed = discord.Embed(
            title="🎲 Your Bingo Sheet is Ready!",
            description=f"Text placed at `{position}` ✅",
            color=0x00ffcc
        )
        embed.set_image(url="attachment://bingo.png")
        await message.channel.send(embed=embed, file=file)

    elif content.startswith(".bingocomplete"):
        if "sheet" not in bingo_state or "path" not in bingo_state:
            embed = discord.Embed(
                title="⚠️ Incomplete Bingo Sheet",
                description="You must use `.bingo <position> <text>` before completing it. 🛑",
                color=0xff5555
            )
            await message.channel.send(embed=embed)
            return

        guild = discord.utils.get(bot.guilds)
        if not guild:
            await message.channel.send("❌ Error: No guilds found.")
            return

        channel = guild.get_channel(CHANNEL_ID)
        if not channel:
            await message.channel.send("❌ Error: Channel not found.")
            return

        path = bingo_state["path"]
        if not os.path.exists(path):
            await message.channel.send("⚠️ No bingo image found. Use `.bingo` first.")
            return

        file = discord.File(path, filename="bingo.png")
        embed = discord.Embed(
            title="📡 Bingo Sheet Submitted!",
            description="Here is the completed bingo sheet 🎉",
            color=0x00cc66
        )
        embed.set_image(url="attachment://bingo.png")
        await channel.send(embed=embed, file=file)

        confirm = discord.Embed(
            title="✅ Bingo Sent!",
            description=f"Your bingo sheet was posted to <#{CHANNEL_ID}> 🏁",
            color=0x00ffcc
        )
        await message.channel.send(embed=confirm)

bot.run(os.getenv("DISCORD_TOKEN"))
