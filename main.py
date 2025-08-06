import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
import os
import json
from pathlib import Path
import textwrap

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

def load_state():
    if not os.path.exists(DATA_FILE):
        return {"sent_commands": False}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_state(state):
    with open(DATA_FILE, "w") as f:
        json.dump(state, f)

pos_map = {
    "topleft": (0, 0), "top": (0, 1), "topright": (0, 2),
    "left": (1, 0), "center": (1, 1), "right": (1, 2),
    "bottomleft": (2, 0), "bottom": (2, 1), "bottomright": (2, 2),
}

def wrap_text_centered(draw, text, font, box_width, box_height):
    # Wrap text using textwrap, approximate char width
    max_chars_per_line = max(1, box_width // bbox = draw.textbbox((0, 0), text, font=font)
width = bbox[2] - bbox[0]
height = bbox[3] - bbox[1]
)[0])
    lines = textwrap.wrap(text, width=max_chars_per_line)

    # Calculate total height of text block
    line_height = font.getsize("Ay")[1]
    total_height = line_height * len(lines)

    y_text = (box_height - total_height) / 2
    return lines, y_text, line_height
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
    if not isinstance(message.channel, discord.DMChannel):
        return

    if message.author.id != OWNER_ID:
        # Track PNG submissions from any user, including owner
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
        elif content.startswith(".bingocomplete"):
            await handle_bingocomplete(message)
        else:
            await handle_bingo(message)

    elif content.startswith(".complete") or content.startswith(".fail"):
        await handle_complete_fail(message)

async def handle_bingo(message):
    parts = message.content.split(maxsplit=2)
    if len(parts) < 3:
        await message.channel.send(embed=discord.Embed(
            description="❌ Usage: `.bingo <position> <text>`",
            color=0xFF0000
        ))
        return

    position = parts[1].lower()
    custom_text = parts[2][:30]  # Limit length

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

async def draw_and_save_bingo(sheet, gray_positions, save_path):
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
            fill_color = "gray" if (r, c) in gray_positions else "white"
            draw.rounded_rectangle(box, radius=20, fill=fill_color, outline="black", width=4)

            text = sheet[r][c]
            if text:
                font = ImageFont.truetype(str(font_path), 36)
                lines, y_text, line_height = wrap_text_centered(draw, text, font, cell_size - 20, cell_size - 20)
                current_y = y + y_text
                for line in lines:
                    w, h = draw.textsize(line, font=font)
                    text_x = x + (cell_size - w) / 2
                    draw.text((text_x, current_y), line, font=font, fill="black")
                    current_y += h

    img.save(save_path)

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
completed_positions = {}  # user_id: list of (row, col)

def check_bingo_win(gray_positions):
    # Check rows and cols
    for i in range(3):
        if all((i, j) in gray_positions for j in range(3)):
            return True
        if all((j, i) in gray_positions for j in range(3)):
            return True
    # Check diagonals
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
            title="✅ Field Completed!",
            description=f"The position `{position}` was marked as **complete**! 🎉",
            color=0x00ccff
        )
        embed.set_image(url="attachment://bingo.png")

        try:
            last_msg_id = message_cache.get(user_id)
            if last_msg_id:
                last_msg = await target_user.fetch_message(last_msg_id)
                await last_msg.edit(embed=embed, attachments=[file])
            else:
                sent = await target_user.send(embed=embed, file=file)
                message_cache[user_id] = sent.id
        except Exception:
            sent = await target_user.send(embed=embed, file=file)
            message_cache[user_id] = sent.id

        if check_bingo_win(gray_list):
            win_embed = discord.Embed(
                title="🏆 Bingo Completed!",
                description="You got 3 in a row! Congratulations! 🎊🎉",
                color=0xFFD700
            )
            await target_user.send(embed=win_embed)

        confirm = discord.Embed(
            title="✅ User Updated!",
            description=f"Marked `{position}` as completed for <@{user_id}> 💪",
            color=0x00ff00
        )
        await message.channel.send(embed=confirm)

    elif message.content.startswith(".fail"):
        embed = discord.Embed(
            title="❌ Field Rejected",
            description=f"The position `{position}` did **not** meet the requirements. 😕\nPlease try again later! 📷",
            color=0xFF0000
        )
        embed.set_footer(text="Better luck next time 🍀")
        try:
            await target_user.send(embed=embed)
        except:
            pass

        confirm = discord.Embed(
            title="📪 Rejection Sent!",
            description=f"Rejected `{position}` for <@{user_id}> ❌",
            color=0xFF9900
        )
        await message.channel.send(embed=confirm)

bot.run(os.getenv("DISCORD_TOKEN"))
