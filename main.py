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

bingo_state = {}
submissions = set()
completed_positions = {}
dm_message_ids = {}

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
        bbox = font.getbbox(test_line)
        test_width = bbox[2] - bbox[0]
        if test_width <= max_width:
            line = test_line
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines

pos_map = {
    "topleft": (0, 0), "top": (0, 1), "topright": (0, 2),
    "left": (1, 0), "center": (1, 1), "right": (1, 2),
    "bottomleft": (2, 0), "bottom": (2, 1), "bottomright": (2, 2),
}

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}!")
    state = load_state()
    if not state.get("sent_commands", False):
        owner = await bot.fetch_user(OWNER_ID)
        embed = discord.Embed(
            title="🤖 Bot Commands",
            description=(
                "**Available Commands:**\n\n"
                "🎯 `.bingo <position> <text>` – Create bingo sheet\n"
                "🧹 `.bingodelete` – Clear bingo sheet\n"
                "📡 `.bingocomplete` – Send bingo to server\n"
                "✅ `.complete <position> <UserID>` – Mark field complete\n"
                "❌ `.fail <position> <UserID>` – Reject field\n"
            ),
            color=0x5865F2
        )
        embed.set_footer(text="Commands only for bot owner 👑")
        await owner.send(embed=embed)
        state["sent_commands"] = True
        save_state(state)

@bot.event
async def on_message(message):
    if not isinstance(message.channel, discord.DMChannel):
        return

    if message.author.id != OWNER_ID:
        if message.attachments:
            for attachment in message.attachments:
                if attachment.filename.lower().endswith(".png"):
                    submissions.add(message.author.id)
                    print(f"✅ PNG received from {message.author.id}")
        return

    content = message.content.strip()

    if content.startswith(".bingo"):
        if content.startswith(".bingodelete"):
            await handle_bingodelete(message)
            return
        elif content.startswith(".bingocomplete"):
            await handle_bingocomplete(message)
            return
        else:
            await handle_bingo(message)
            return

    if content.startswith(".complete") or content.startswith(".fail"):
        await handle_complete_fail(message)

async def handle_bingo(message):
    parts = message.content.split(maxsplit=2)
    if len(parts) < 3:
        await message.channel.send("❌ Usage: `.bingo <position> <text>`")
        return

    position = parts[1].lower()
    custom_text = parts[2][:15]

    if position not in pos_map:
        await message.channel.send("❌ Invalid position. Try: `top`, `center`, `bottomright`, etc.")
        return

    row, col = pos_map[position]
    sheet = bingo_state.get("sheet", [["" for _ in range(3)] for _ in range(3)])
    sheet[row][col] = custom_text

    bingo_state["sheet"] = sheet
    bingo_state["author"] = message.author.name
    bingo_state["path"] = f"/tmp/bingo_{message.author.id}.png"

    await draw_bingo_sheet(sheet, [], bingo_state["path"])

    file = discord.File(bingo_state["path"], filename="bingo.png")
    embed = discord.Embed(
        title="🎲 Your Bingo Sheet is Ready!",
        description=f"✅ Text placed at `{position}`.",
        color=0x00ffcc
    )
    embed.set_image(url="attachment://bingo.png")
    await message.channel.send(embed=embed, file=file)
async def draw_bingo_sheet(sheet, gray_positions, save_path):
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
                    text_width = bbox[2] - bbox[0]
                    if text_width <= cell_size - 20:
                        break
                    font_size -= 2

                lines = wrap_text(text, font, cell_size - 20)
                for i, line in enumerate(lines):
                    text_width = font.getbbox(line)[2] - font.getbbox(line)[0]
                    text_height = font.getbbox(line)[3] - font.getbbox(line)[1]
                    text_x = x + (cell_size - text_width) / 2
                    text_y = y + (cell_size - len(lines) * text_height) / 2 + i * text_height
                    draw.text((text_x, text_y), line, font=font, fill="black")

            if (r, c) in gray_positions:
                overlay = Image.new("RGBA", (cell_size, cell_size), (128, 128, 128, 160))
                img.paste(overlay, (x, y), overlay)

    img.save(save_path)

def check_bingo_win(gray):
    for i in range(3):
        if all((i, j) in gray for j in range(3)) or all((j, i) in gray for j in range(3)):
            return True
    if all((i, i) in gray for i in range(3)) or all((i, 2 - i) in gray for i in range(3)):
        return True
    return False

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

    file = discord.File(bingo_state["path"], filename="bingo.png")
    embed = discord.Embed(
        title="📡 Bingo Sheet Submitted!",
        description="The bingo sheet has been posted! 🎉",
        color=0x00cc66
    )
    embed.set_image(url="attachment://bingo.png")
    sent = await channel.send(embed=embed, file=file)

    dm_message_ids[bingo_state["author"]] = sent.id

    confirm = discord.Embed(
        title="✅ Bingo Sent!",
        description=f"Posted to <#{CHANNEL_ID}> 🎯",
        color=0x00ffcc
    )
    await message.channel.send(embed=confirm)

async def handle_bingodelete(message):
    bingo_state["sheet"] = [["" for _ in range(3)] for _ in range(3)]
    bingo_state["path"] = "/tmp/bingo_deleted.png"
    await draw_bingo_sheet(bingo_state["sheet"], [], bingo_state["path"])

    file = discord.File(bingo_state["path"], filename="bingo_deleted.png")
    embed = discord.Embed(
        title="🧹 Bingo Cleared!",
        description="All text has been removed from the bingo sheet! 🧼",
        color=0xFF6347
    )
    embed.set_image(url="attachment://bingo_deleted.png")
    await message.channel.send(embed=embed, file=file)
async def handle_complete_fail(message):
    parts = message.content.split()
    if message.content.startswith(".complete"):
        if len(parts) != 3 or parts[1].lower() not in pos_map or not parts[2].isdigit():
            await message.channel.send("❌ Usage: `.complete <position> <UserID>`")
            return

        position = parts[1].lower()
        user_id = int(parts[2])
        if user_id not in submissions:
            await message.channel.send("🚫 That user has not submitted a PNG image yet.")
            return

        try:
            target_user = await bot.fetch_user(user_id)
            row, col = pos_map[position]
            gray_list = completed_positions.setdefault(user_id, [])
            if (row, col) not in gray_list:
                gray_list.append((row, col))

            sheet = bingo_state.get("sheet", [["" for _ in range(3)] for _ in range(3)])
            user_path = f"/tmp/bingo_user_{user_id}.png"
            await draw_bingo_sheet(sheet, gray_list, user_path)

            file = discord.File(user_path, filename="bingo.png")
            embed = discord.Embed(
                title="✅ Field Completed!",
                description=f"The position `{position}` was marked as **complete**! 🎉",
                color=0x00ccff
            )
            embed.set_image(url="attachment://bingo.png")

            if user_id in dm_message_ids:
                msg_id = dm_message_ids[user_id]
                try:
                    last_msg = await target_user.fetch_message(msg_id)
                    await last_msg.edit(embed=embed, attachments=[file])
                except:
                    sent = await target_user.send(embed=embed, file=file)
                    dm_message_ids[user_id] = sent.id
            else:
                sent = await target_user.send(embed=embed, file=file)
                dm_message_ids[user_id] = sent.id

            if check_bingo_win(gray_list):
                win = discord.Embed(
                    title="🏆 Bingo Completed!",
                    description="You got 3 in a row! Congratulations! 🎊🎉",
                    color=0xFFD700
                )
                await target_user.send(embed=win)

            confirm = discord.Embed(
                title="✅ User Updated!",
                description=f"Marked `{position}` as completed for <@{user_id}> 💪",
                color=0x00ff00
            )
            await message.channel.send(embed=confirm)

        except Exception as e:
            await message.channel.send(f"❌ Error: {e}")

    elif message.content.startswith(".fail"):
        if len(parts) != 3 or parts[1].lower() not in pos_map or not parts[2].isdigit():
            await message.channel.send("❌ Usage: `.fail <position> <UserID>`")
            return

        position = parts[1].lower()
        user_id = int(parts[2])
        try:
            target_user = await bot.fetch_user(user_id)
            embed = discord.Embed(
                title="❌ Field Rejected",
                description=f"The position `{position}` did **not** meet the requirements. 😕\nPlease try again later! 📷",
                color=0xFF0000
            )
            embed.set_footer(text="Better luck next time 🍀")
            await target_user.send(embed=embed)

            confirm = discord.Embed(
                title="📪 Rejection Sent!",
                description=f"Rejected `{position}` for <@{user_id}> ❌",
                color=0xFF9900
            )
            await message.channel.send(embed=confirm)

        except Exception as e:
            await message.channel.send(f"❌ Error: {e}")

# Start the bot
bot.run(os.getenv("DISCORD_TOKEN"))
