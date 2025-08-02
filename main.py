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

def load_state():
    if not os.path.exists(DATA_FILE):
        return {"sent_commands": False}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_state(state):
    with open(DATA_FILE, "w") as f:
        json.dump(state, f)

def wrap_text(text, font, max_width):
    lines = []
    words = text.split()
    line = ""
    
    for word in words:
        test_line = f"{line} {word}".strip()
        bbox = font.getbbox(test_line)  # Use getbbox for better text sizing
        test_width = bbox[2] - bbox[0]  # Calculate text width
        if test_width <= max_width:
            line = test_line
        else:
            if line:  # If the line is not empty, add it to the lines list
                lines.append(line)
            line = word  # Start a new line with the current word
    if line:
        lines.append(line)  # Add the final line
    return lines

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
                "🧹 `.bingodelete` – Delete all text from the bingo sheet\n"
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

    content = message.content.strip()

    # Verarbeite die Bingo-Befehle explizit und überprüfe zuerst auf die genauen Befehle
    if content.startswith(".bingo"):
        if content.startswith(".bingodelete"):
            await handle_bingodelete(message)
            return
        elif content.startswith(".bingocomplete"):
            await handle_bingocomplete(message)
            return
        elif content.startswith(".bingo"):
            await handle_bingo(message)
            return

    # Für andere Befehle wie .complete und .fail
    if content.startswith(".complete") or content.startswith(".fail"):
        await handle_complete_fail(message)

async def handle_bingo(message):
    parts = message.content.split(maxsplit=2)
    if len(parts) < 3:
        await message.channel.send("❌ Usage: `.bingo <position> <text>`")
        return

    position = parts[1].lower()
    custom_text = parts[2][:15]
    pos_map = {
        "topleft": (0, 0), "top": (0, 1), "topright": (0, 2),
        "left": (1, 0), "center": (1, 1), "right": (1, 2),
        "bottomleft": (2, 0), "bottom": (2, 1), "bottomright": (2, 2),
    }

    if position not in pos_map:
        await message.channel.send("❌ Invalid position! Try: topleft, top, center, etc.")
        return

    row, col = pos_map[position]

    # Create or load previous sheet
    if "sheet" in bingo_state:
        sheet = bingo_state["sheet"]
    else:
        sheet = [["" for _ in range(3)] for _ in range(3)]

    # Set custom text in the requested position
    sheet[row][col] = custom_text

    bingo_state["sheet"] = sheet
    bingo_state["author"] = message.author.name
    bingo_state["path"] = f"/tmp/bingo_{message.author.id}.png"

    cell_size = 160
    padding = 10
    img_size = 3 * cell_size + 2 * padding
    img = Image.new("RGB", (img_size, img_size), color=(240, 240, 240))
    draw = ImageDraw.Draw(img)
    font_path = Path("fonts/DejaVuSans.ttf")

    for r in range(3):
        for c in range(3):
            x = c * cell_size + padding
            y = r * cell_size + padding
            box = [x, y, x + cell_size, y + cell_size]
            draw.rounded_rectangle(box, radius=20, fill="white", outline="black", width=4)

            text = sheet[r][c]
            if text:
                font_size = 44
                while font_size > 10:
                    try:
                        font = ImageFont.truetype(str(font_path), font_size)
                    except:
                        font = ImageFont.load_default()
                    bbox = font.getbbox(text)
                    text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    if text_width <= cell_size - 20:
                        break
                    font_size -= 2

                text_x = x + (cell_size - text_width) / 2
                text_y = y + (cell_size - text_height) / 2
                fill_color = "black"
                
                # Use wrap_text to handle multi-line text
                lines = wrap_text(text, font, cell_size - 20)
                for i, line in enumerate(lines):
                    text_y = y + (cell_size - len(lines) * text_height) / 2 + i * text_height
                    draw.text((text_x, text_y), line, font=font, fill=fill_color)

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

async def handle_bingodelete(message):
    # Clear all text in the Bingo sheet
    bingo_state["sheet"] = [["" for _ in range(3)] for _ in range(3)]
    bingo_state["path"] = "/tmp/bingo_deleted.png"
    
    # Create empty bingo sheet
    cell_size = 160
    padding = 10
    img_size = 3 * cell_size + 2 * padding
    img = Image.new("RGB", (img_size, img_size), color=(240, 240, 240))
    draw = ImageDraw.Draw(img)

    for r in range(3):
        for c in range(3):
            x = c * cell_size + padding
            y = r * cell_size + padding
            box = [x, y, x + cell_size, y + cell_size]
            draw.rounded_rectangle(box, radius=20, fill="white", outline="black", width=4)

    path = bingo_state["path"]
    img.save(path)

    file = discord.File(path, filename="bingo_deleted.png")
    embed = discord.Embed(
        title="🧹 Bingo Sheet Cleared!",
        description="All text in your Bingo sheet has been cleared. 🧼",
        color=0xFF6347
    )
    embed.set_image(url="attachment://bingo_deleted.png")
    await message.channel.send(embed=embed, file=file)

async def handle_bingocomplete(message):
    if "sheet" not in bingo_state or "path" not in bingo_state:
        await message.channel.send("⚠️ Use `.bingo` first!")
        return

    guild = discord.utils.get(bot.guilds)
    if not guild:
        await message.channel.send("❌ No guilds found.")
        return

    channel = guild.get_channel(CHANNEL_ID)
    if not channel:
        await message.channel.send("❌ Channel not found.")
        return

    path = bingo_state["path"]
    if not os.path.exists(path):
        await message.channel.send("⚠️ Bingo image not found.")
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
        description=f"Posted to <#{CHANNEL_ID}> 🏋️",
        color=0x00ffcc
    )
    await message.channel.send(embed=confirm)

async def handle_complete_fail(message):
    parts = message.content.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.channel.send("❌ Invalid usage! Use `.complete <UserID>` or `.fail <UserID>`.") 
        return

    user_id = int(parts[1])
    try:
        target_user = await bot.fetch_user(user_id)

        if message.content.startswith(".complete"):
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

        elif message.content.startswith(".fail"):
            fail_embed = discord.Embed(
                title="❌ Submission Failed",
                description="😕 Your picture did not meet the requirements.\nPlease try again later. 📷",
                color=0xff0000
            )
            fail_embed.set_footer(text="Better luck next time 🍀")
            await target_user.send(embed=fail_embed)

            confirm = discord.Embed(
                title="📪 Message Sent!",
                description=f"Failure message sent to <@{user_id}> ❌",
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
