# bingo_bot.py
import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
import os
import json
import textwrap
import io
import asyncio

# ---------- CONFIG ----------
TOKEN = "YOUR_DISCORD_BOT_TOKEN_HERE"  # replace or set via env in production
COMMAND_PREFIX = "."
SHEETS_DIR = "sheets"  # will store JSON + master PNG per creator
FONT_PATH = None  # leave None to use PIL's default font; you can set a TTF path for nicer fonts
FONT_SIZE = 28
# ----------------------------

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)

# Ensure sheets dir exists
os.makedirs(SHEETS_DIR, exist_ok=True)

# Position to cell mapping (row, col) for convenience
POSITIONS = {
    "topleft": (0, 0),
    "top": (0, 1),
    "topright": (0, 2),
    "middleleft": (1, 0),
    "middle": (1, 1),
    "middleright": (1, 2),
    "bottomleft": (2, 0),
    "bottom": (2, 1),
    "bottomright": (2, 2),
}

# Canvas settings
CANVAS_WIDTH = 900
CANVAS_HEIGHT = 900
PADDING = 40
CELL_GAP = 10
CELL_RADIUS = 25  # rounded corners (approx)
CELL_LINE_WIDTH = 8
CELL_COLOR = (255, 255, 255)
GRID_LINE_COLOR = (0, 0, 0)
GREY_OUT = (180, 180, 180, 200)  # RGBA overlay for completed cells

def load_font(size=FONT_SIZE):
    if FONT_PATH and os.path.isfile(FONT_PATH):
        return ImageFont.truetype(FONT_PATH, size)
    else:
        try:
            return ImageFont.truetype("arial.ttf", size)
        except Exception:
            return ImageFont.load_default()

def sheet_paths_for_user(user_id: int):
    json_path = os.path.join(SHEETS_DIR, f"{user_id}.json")
    png_path = os.path.join(SHEETS_DIR, f"{user_id}.png")
    return json_path, png_path

def save_sheet_json(user_id: int, data: dict):
    path, _ = sheet_paths_for_user(user_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_sheet_json(user_id: int):
    path, _ = sheet_paths_for_user(user_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def wrap_text_to_fit(draw, text, font, max_width):
    """
    Wrap the text into multiple lines so that each line fits max_width.
    """
    # First split by existing line breaks
    lines = []
    for para in text.splitlines():
        # try progressively larger chunks using textwrap
        wrapped = textwrap.wrap(para, width=100)
        # shrink width until fits
        final_wrapped = []
        for wline in wrapped:
            # further split so it fits
            if draw.textbbox((0,0), wline, font=font)[2] <= max_width:
                final_wrapped.append(wline)
            else:
                # brute force char-by-char split
                cur = ""
                for ch in wline:
                    cur += ch
                    if draw.textbbox((0,0), cur, font=font)[2] > max_width:
                        # remove last char to keep under limit
                        final_wrapped.append(cur[:-1])
                        cur = ch
                if cur:
                    final_wrapped.append(cur)
        lines.extend(final_wrapped if final_wrapped else [para])
    return lines

def generate_sheet_image(cells: list, completed_positions: set):
    """
    cells: list of 9 strings in row-major order
    completed_positions: set of position keys (like 'topleft') to gray out
    Returns a PIL Image object.
    """
    canvas = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (50, 50, 50, 255))
    draw = ImageDraw.Draw(canvas)
    font = load_font(FONT_SIZE)

    grid_w = CANVAS_WIDTH - 2 * PADDING
    grid_h = CANVAS_HEIGHT - 2 * PADDING
    cell_w = (grid_w - (2 * CELL_GAP)) // 3
    cell_h = (grid_h - (2 * CELL_GAP)) // 3

    # Draw white background rounded rectangle for grid area
    # (we'll draw cells individually with rounded corners)
    for row in range(3):
        for col in range(3):
            x0 = PADDING + col * (cell_w + CELL_GAP)
            y0 = PADDING + row * (cell_h + CELL_GAP)
            x1 = x0 + cell_w
            y1 = y0 + cell_h

            # outer black border rounded rect
            # draw rounded rectangle by drawing rounded rect (newer Pillow versions)
            try:
                draw.rounded_rectangle([(x0, y0), (x1, y1)], radius=CELL_RADIUS,
                                       fill=CELL_COLOR, outline=GRID_LINE_COLOR, width=CELL_LINE_WIDTH)
            except Exception:
                # Fallback: draw a normal rect if rounded not available
                draw.rectangle([(x0, y0), (x1, y1)], fill=CELL_COLOR, outline=GRID_LINE_COLOR, width=CELL_LINE_WIDTH)

            # Fill gray overlay if position is in completed_positions
            pos_key = None
            # find position key for this cell
            for k, (r, c) in POSITIONS.items():
                if r == row and c == col:
                    pos_key = k
                    break
            if pos_key and pos_key in completed_positions:
                # create overlay
                overlay = Image.new("RGBA", (cell_w, cell_h), GREY_OUT)
                canvas.paste(overlay, (x0, y0), overlay)

            # Draw the text, wrapped to fit inside cell
            idx = row * 3 + col
            text = cells[idx] if idx < len(cells) else ""
            # compute inner padding for text
            tpad_x = 12
            tpad_y = 12
            inner_w = cell_w - 2 * tpad_x
            inner_h = cell_h - 2 * tpad_y
            lines = wrap_text_to_fit(draw, text, font, inner_w)
            # compute vertical centering
            text_height_total = sum([draw.textbbox((0,0), ln, font=font)[3] - draw.textbbox((0,0), ln, font=font)[1] for ln in lines])
            # spacing between lines
            line_spacing = 6
            text_height_total += (len(lines)-1)*line_spacing
            start_y = y0 + (cell_h - text_height_total) // 2
            for ln in lines:
                bbox = draw.textbbox((0,0), ln, font=font)
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
                x = x0 + (cell_w - w) // 2
                draw.text((x, start_y), ln, fill=(0,0,0), font=font)
                start_y += h + line_spacing

    # Return RGB image
    return canvas.convert("RGB")

# ---------- Commands ----------

@bot.event
async def on_ready():
    print(f"Bot ready as {bot.user} (id: {bot.user.id})")
    try:
        await bot.change_presence(activity=discord.Game(name="Bingo! Type .help"))
    except Exception:
        pass

@bot.command(name="help")
async def help_cmd(ctx):
    embed = discord.Embed(title="Bingo Bot Commands 🟩🟦", color=discord.Color.green())
    embed.add_field(name=".bingocomplete <9 items>", value=(
        "Create & save a 3×3 Bingo sheet. You can supply 9 items separated by commas, or a multi-line block (each line an item). "
        "Example:\n`.bingocomplete apples, oranges, bananas, kiwi, mango, grape, pear, plum, lemon`\n\n"
        "If you provide fewer than 9 items the rest will be blank."
    ), inline=False)
    embed.add_field(name=".complete <position> <target_user_id>", value=(
        "Mark a position as completed (gray it out) and send the updated sheet to the target user via DM.\n"
        "Positions: topleft, top, topright, middleleft, middle, middleright, bottomleft, bottom, bottomright\n\n"
        "Example: `.complete topleft 123456789012345678`"
    ), inline=False)
    embed.set_footer(text="Made with ❤️ — Bingo Bot")
    await ctx.send(embed=embed)

@bot.command(name="bingocomplete")
async def bingocomplete(ctx, *, items: str = None):
    """
    Create and save a bingo sheet for the invoking user.
    """
    author = ctx.author
    # parse items: allow comma-separated or newline-separated
    parsed = []
    if items:
        # split by newline OR comma
        if "\n" in items:
            parsed = [i.strip() for i in items.splitlines() if i.strip()][:9]
        else:
            # comma separated probably
            parsed = [i.strip() for i in items.split(",") if i.strip()][:9]

    # pad to 9
    while len(parsed) < 9:
        parsed.append("")

    # save json state (cells + completed set)
    json_path, png_path = sheet_paths_for_user(author.id)
    state = {
        "author_id": author.id,
        "cells": parsed,
        "completed": [],  # list of position keys
    }
    save_sheet_json(author.id, state)

    # generate and save the base image
    img = generate_sheet_image(parsed, set())
    img.save(png_path, format="PNG")

    embed = discord.Embed(title="Bingo sheet saved ✅", description=f"{author.mention}, your sheet was created and saved! 📥", color=discord.Color.blue())
    embed.add_field(name="How to mark a position", value="Use `.complete <position> <target_user_id>` to gray out a position and send the updated sheet to a user. 👍", inline=False)
    # attach image
    with io.BytesIO() as buf:
        img.save(buf, format="PNG")
        buf.seek(0)
        file = discord.File(buf, filename="bingo_sheet.png")
        embed.set_image(url="attachment://bingo_sheet.png")
        await ctx.send(embed=embed, file=file)

@bot.command(name="complete")
async def complete_cmd(ctx, position: str = None, target_user_id: str = None):
    """
    .complete <position> <user_id>
    Marks the saved sheet of the author as having 'position' completed, regenerates the image, saves state,
    and DMs the generated image to the target user ID.
    """
    if position is None or target_user_id is None:
        embed = discord.Embed(title="Usage ❗", description="`.complete <position> <target_user_id>`\nSee `.help` for more.", color=discord.Color.red())
        await ctx.send(embed=embed)
        return

    pos_key = position.lower()
    if pos_key not in POSITIONS:
        embed = discord.Embed(title="Invalid position ❗", description=f"Position `{position}` is not recognized.\nValid: {', '.join(POSITIONS.keys())}", color=discord.Color.red())
        await ctx.send(embed=embed)
        return

    # try to parse target user id
    try:
        target_uid = int(target_user_id.strip("<@!> "))
    except Exception:
        embed = discord.Embed(title="Invalid user id ❗", description="Please supply a valid user ID (numbers only).", color=discord.Color.red())
        await ctx.send(embed=embed)
        return

    # load sheet of the invoking user (the instructions said the saved sheet produced by .bingocomplete should be used)
    author_id = ctx.author.id
    state = load_sheet_json(author_id)
    if not state:
        embed = discord.Embed(title="No saved sheet ❗", description="You do not have a saved sheet. Create one with `.bingocomplete` first.", color=discord.Color.red())
        await ctx.send(embed=embed)
        return

    # Update completed set
    completed = set(state.get("completed", []))
    # Add new position (cumulative)
    completed.add(pos_key)
    state["completed"] = list(completed)
    save_sheet_json(author_id, state)

    # Generate updated image
    cells = state.get("cells", [""]*9)
    img = generate_sheet_image(cells, completed)

    # Save updated base PNG as the latest representation (so that the original isn't repeatedly re-sent)
    _, png_path = sheet_paths_for_user(author_id)
    img.save(png_path, format="PNG")

    # Send the updated image to the target user via DM
    target_member = ctx.guild.get_member(target_uid) if ctx.guild else None
    dm_sent = False
    try:
        user_obj = bot.get_user(target_uid) or (await bot.fetch_user(target_uid))
        with io.BytesIO() as buf:
            img.save(buf, format="PNG")
            buf.seek(0)
            file = discord.File(buf, filename="bingo_completed.png")
            embed = discord.Embed(title="Bingo Sheet Update 🎉", description=f"<@{author_id}>'s bingo sheet has been updated. Position **{pos_key}** has been marked as completed. ✅", color=discord.Color.green())
            embed.set_footer(text="Bingo Bot • Delivered via DM 📩")
            embed.set_image(url="attachment://bingo_completed.png")
            await user_obj.send(embed=embed, file=file)
            dm_sent = True
    except discord.Forbidden:
        dm_sent = False
    except Exception as e:
        dm_sent = False
        print("Error sending DM:", e)

    if dm_sent:
        embed_ok = discord.Embed(title="Success ✅", description=f"Updated sheet was sent to <@{target_uid}> via DM. 📩", color=discord.Color.green())
        await ctx.send(embed=embed_ok)
    else:
        embed_fail = discord.Embed(title="Could not DM user ⚠️", description=f"Couldn't DM <@{target_uid}>. They may have DMs disabled. The updated sheet was saved.", color=discord.Color.orange())
        # attach the image to the channel as fallback
        with io.BytesIO() as buf:
            img.save(buf, format="PNG")
            buf.seek(0)
            file = discord.File(buf, filename="bingo_completed.png")
            embed_fail.set_image(url="attachment://bingo_completed.png")
            await ctx.send(embed=embed_fail, file=file)

# Run the bot
if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))
