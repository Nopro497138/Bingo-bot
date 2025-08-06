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
message_cache = {}

pos_map = {
    "topleft": (0, 0), "top": (0, 1), "topright": (0, 2),
    "left": (1, 0), "center": (1, 1), "right": (1, 2),
    "bottomleft": (2, 0), "bottom": (2, 1), "bottomright": (2, 2),
}

def load_state():
    if not os.path.exists(DATA_FILE):
        return {"sent_commands": False}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_state(state):
    with open(DATA_FILE, "w") as f:
        json.dump(state, f)

def fit_text_to_box(draw, text, font_path, max_width, max_height, max_font_size=44, min_font_size=10):
    """
    Find the biggest font size so that the text fits into max_width x max_height box.
    Returns: (font, lines, line_height)
    """
    font_size = max_font_size
    while font_size >= min_font_size:
        try:
            font = ImageFont.truetype(str(font_path), font_size)
        except Exception:
            font = ImageFont.load_default()

        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            bbox_line = draw.textbbox((0, 0), test_line, font=font)
            line_width = bbox_line[2] - bbox_line[0]
            if line_width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        bbox = draw.textbbox((0, 0), "Ay", font=font)
        line_height = (bbox[3] - bbox[1]) * 1.2
        total_height = line_height * len(lines)

        if total_height <= max_height:
            return font, lines, line_height

        font_size -= 2

    font = ImageFont.truetype(str(font_path), min_font_size)
    return font, [text], min_font_size * 1.2
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}!")
    state = load_state()
    if not state.get("sent_commands", False):
        owner = await bot.fetch_user(OWNER_ID)
        embed = discord.Embed(
            title="🤖 Bot Commands",
            description=(
                "**Available commands:**\n\n"
                "✅ `.complete <position> <userID>` – Mark a bingo field as complete\n"
                "❌ `.fail <position> <userID>` – Reject a user submission\n"
                "🎯 `.bingo <position> <text>` – Add text to bingo sheet\n"
                "🧹 `.bingodelete` – Clear the sheet\n"
                "📡 `.bingocomplete` – Post to channel"
            ),
            color=0x7289da
        )
        embed.set_footer(text="Commands are owner-only 👑")
        await owner.send(embed=embed)
        state["sent_commands"] = True
        save_state(state)

@bot.event
async def on_message(message):
    # Forward PNG images sent by users to OWNER in an embed with emojis
    if isinstance(message.channel, discord.DMChannel) and message.author.id != OWNER_ID:
        if message.attachments:
            for attachment in message.attachments:
                if attachment.filename.lower().endswith(".png"):
                    submissions.add(message.author.id)
                    owner = await bot.fetch_user(OWNER_ID)
                    embed = discord.Embed(
                        title="📥 New PNG Submission!",
                        description=(
                            f"User: {message.author} (`{message.author.id}`) has sent a PNG image! 🎉\n"
                            f"Please review their submission."
                        ),
                        color=0x00ffcc
                    )
                    embed.set_image(url=attachment.url)
                    embed.set_footer(text="Use .complete or .fail commands to respond.")
                    await owner.send(embed=embed)
        return

    # Only OWNER can use commands
    if message.author.id != OWNER_ID:
        return

    content = message.content.strip()

    if content.startswith(".bingo"):
        if content.startswith(".bingodelete"):
            await handle_bingodelete(message)
        elif content.startswith(".bingocomplete"):
            await handle_bingocomplete(message)
        else:
            await handle_bingo(message)

    elif content.startswith(".complete") or content.startswith(".fail"):
        await handle_complete_fail(message)


async def draw_and_save_bingo(sheet, gray_positions, save_path):
    cell_size = 160
    padding = 10
    img_size = 3 * cell_size + 2 * padding
    img = Image.new("RGB", (img_size, img_size), color=(230, 230, 230))
    draw = ImageDraw.Draw(img)
    font_path = Path("fonts/DejaVuSans.ttf")

    for r in range(3):
        for c in range(3):
            x = c * cell_size + padding
            y = r * cell_size + padding
            box = [x, y, x + cell_size, y + cell_size]

            base_color = (255, 255, 255)
            if (r, c) in gray_positions:
                base_color = (170, 170, 170)

            # Draw cell background with a subtle gradient
            for i in range(cell_size):
                blend = int(base_color[0] * (1 - i/cell_size) + 200 * (i/cell_size))
                for px in range(cell_size):
                    img.putpixel((x+px, y+i), (blend, blend, blend))

            draw.rounded_rectangle(box, radius=20, fill=None, outline="black", width=3)

            text = sheet[r][c]
            if text:
                font, lines, line_height = fit_text_to_box(draw, text, font_path, cell_size - 24, cell_size - 24)
                current_y = y + (cell_size - line_height * len(lines)) / 2
                for line in lines:
                    bbox = draw.textbbox((0, 0), line, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_x = x + (cell_size - text_width) / 2
                    draw.text((text_x, current_y), line, font=font, fill="black")
                    current_y += line_height

    img.save(save_path)


async def handle_bingo(message):
    parts = message.content.split(maxsplit=2)
    if len(parts) < 3:
        await message.channel.send(embed=discord.Embed(
            description="❌ Usage: `.bingo <position> <text>`",
            color=0xFF0000
        ))
        return

    position = parts[1].lower()
    custom_text = parts[2][:50]

    if position not in pos_map:
        await message.channel.send(embed=discord.Embed(
            description="❌ Invalid position! Use: topleft, top, center, etc.",
            color=0xFF0000
        ))
        return

    row, col = pos_map[position]
    sheet = bingo_state.get("sheet", [["" for _ in range(3)] for _ in range(3)])
    sheet[row][col] = custom_text

    bingo_state["sheet"] = sheet
    bingo_state["author"] = message.author.name
    bingo_state["path"] = f"/tmp/bingo_{message.author.id}.png"

    await draw_and_save_bingo(sheet, [], bingo_state["path"])

    file = discord.File(bingo_state["path"], filename="bingo.png")
    embed = discord.Embed(
        title="🎲 Your Bingo Sheet is Ready!",
        description=f"✅ Text placed at `{position}`.",
        color=0x00ffcc
    )
    embed.set_image(url="attachment://bingo.png")
    await message.channel.send(embed=embed, file=file)

async def handle_bingodelete(message):
    bingo_state["sheet"] = [["" for _ in range(3)] for _ in range(3)]
    bingo_state["path"] = "/tmp/bingo_deleted.png"
    await draw_and_save_bingo(bingo_state["sheet"], [], bingo_state["path"])

    file = discord.File(bingo_state["path"], filename="bingo_deleted.png")
    embed = discord.Embed(
        title="🧹 Bingo Sheet Cleared!",
        description="All text has been removed from the bingo sheet! 🧼",
        color=0xFF6347
    )
    embed.set_image(url="attachment://bingo_deleted.png")
    await message.channel.send(embed=embed, file=file)

async def handle_bingocomplete(message):
    if "sheet" not in bingo_state or "path" not in bingo_state:
        await message.channel.send(embed=discord.Embed(
            description="⚠️ Use `.bingo` first!",
            color=0xFF9900
        ))
        return

    guild = discord.utils.get(bot.guilds)
    if not guild:
        await message.channel.send(embed=discord.Embed(
            description="❌ No guilds found.",
            color=0xFF0000
        ))
        return

    channel = guild.get_channel(CHANNEL_ID)
    if not channel:
        await message.channel.send(embed=discord.Embed(
            description="❌ Channel not found.",
            color=0xFF0000
        ))
        return

    file = discord.File(bingo_state["path"], filename="bingo.png")
    embed = discord.Embed(
        title="📡 Bingo Sheet Submitted!",
        description="The bingo sheet has been posted! 🎉",
        color=0x00cc66
    )
    embed.set_image(url="attachment://bingo.png")
    await channel.send(embed=embed, file=file)

    confirm = discord.Embed(
        title="✅ Bingo Sent!",
        description=f"Posted to <#{CHANNEL_ID}> 🎯",
        color=0x00ffcc
    )
    await message.channel.send(embed=confirm)
completed_positions = {}  # user_id -> list of (row, col)

def check_bingo_win(gray_positions):
    # Check rows, columns, diagonals for 3 in a row
    for i in range(3):
        if all((i, j) in gray_positions for j in range(3)):
            return True
        if all((j, i) in gray_positions for j in range(3)):
            return True
    if all((i, i) in gray_positions for i in range(3)):
        return True
    if all((i, 2 - i) in gray_positions for i in range(3)):
        return True
    return False

async def handle_complete_fail(message):
    parts = message.content.split()
    if len(parts) != 3 or parts[1].lower() not in pos_map or not parts[2].isdigit():
        await message.channel.send(embed=discord.Embed(
            description="❌ Usage: `.complete <position> <UserID>` or `.fail <position> <UserID>`",
            color=0xFF0000
        ))
        return

    position = parts[1].lower()
    user_id = int(parts[2])
    row, col = pos_map[position]

    try:
        target_user = await bot.fetch_user(user_id)
    except Exception as e:
        await message.channel.send(embed=discord.Embed(
            description=f"❌ Could not fetch user with ID {user_id}.\nError: {e}",
            color=0xFF0000
        ))
        return

    if message.content.startswith(".complete"):
        gray_list = completed_positions.setdefault(user_id, [])
        if (row, col) not in gray_list:
            gray_list.append((row, col))

        sheet = bingo_state.get("sheet", [["" for _ in range(3)] for _ in range(3)])
        user_path = f"/tmp/bingo_user_{user_id}.png"
        await draw_and_save_bingo(sheet, gray_list, user_path)

        file = discord.File(user_path, filename="bingo.png")
        embed = discord.Embed(
            title="✅ Field Marked Complete! 🎉",
            description=f"Position `{position}` marked as completed for you! 💪",
            color=0x00ccff
        )
        embed.set_image(url="attachment://bingo.png")

        try:
            last_msg_id = message_cache.get(user_id)
            if last_msg_id:
                channel = await target_user.create_dm()
                last_msg = await channel.fetch_message(last_msg_id)
                await last_msg.edit(embed=embed, attachments=[file])
            else:
                sent = await target_user.send(embed=embed, file=file)
                message_cache[user_id] = sent.id
        except Exception:
            sent = await target_user.send(embed=embed, file=file)
            message_cache[user_id] = sent.id

        if check_bingo_win(gray_list):
            win_embed = discord.Embed(
                title="🏆 BINGO! You won! 🎉",
                description="You completed 3 in a row! Congratulations! 🥳",
                color=0xFFD700
            )
            await target_user.send(embed=win_embed)

        confirm = discord.Embed(
            title="✅ User Updated!",
            description=f"Position `{position}` marked as completed for <@{user_id}> 💪",
            color=0x00ff00
        )
        await message.channel.send(embed=confirm)

    elif message.content.startswith(".fail"):
        fail_embed = discord.Embed(
            title="❌ Field Rejected",
            description=f"Your submission for position `{position}` was rejected. 😕 Please try again later! 📷",
            color=0xFF0000
        )
        fail_embed.set_footer(text="Better luck next time 🍀")
        try:
            await target_user.send(embed=fail_embed)
        except:
            pass

        confirm = discord.Embed(
            title="📪 Rejection Sent!",
            description=f"Rejection message sent for `{position}` to <@{user_id}> ❌",
            color=0xFF9900
        )
        await message.channel.send(embed=confirm)

bot.run(os.getenv("DISCORD_TOKEN"))
