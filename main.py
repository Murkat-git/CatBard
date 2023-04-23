import discord
import requests
import base64
from discord.ext import commands

import io
import aiohttp

from tictactoe import TicTacToe
from trivia import Trivia
from music.music import Music
from music.events import MusicEvents

import dotenv
import os

dotenv.load_dotenv()
token = str(os.getenv("TOKEN"))

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=commands.when_mentioned_or("!"), intents=intents)

bot.lavalink_nodes = [
    {"host": "lavalink.lexnet.cc", "port": 443, "password": "lexn3tl@val!nk", "https": True},
    {"host": "eu-lavalink.lexnet.cc", "port": 443, "password": "lexn3tl@val!nk", "https": True},
    {"host": "suki.nathan.to", "port": 443, "password": "adowbongmanacc", "https": True},
    {"host": "lavalink.devamop.in", "port": 443, "password": "DevamOP", "https": True}
]
bot.add_cog(Music(bot))
bot.add_cog(MusicEvents(bot))


async def send_image(ctx, url, name="image.png"):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return await ctx.send('Could not download file...')
            data = io.BytesIO(await resp.read())
            await ctx.send(file=discord.File(data, name))


@bot.slash_command(name="tictactoe")
async def tic(ctx: commands.Context):
    """Starts a tic-tac-toe game with yourself."""
    # Setting the reference message to ctx.message makes the bot reply to the member's message.
    await ctx.delete()
    await ctx.send("Tic Tac Toe: X goes first", view=TicTacToe(), reference=ctx.message)


# @bot.slash_command(name="guess")
# async def guess(ctx: commands.Context, left:discord.Option(int), right:discord.option(int)):
#     await ctx.delete()
#     await ctx.send()

@bot.slash_command(name="trivia")
async def trivia(ctx: commands.Context, amount: discord.Option(int, default=1)):
    await ctx.defer()
    try:
        session_token = requests.get("https://opentdb.com/api_token.php?command=request").json()[
            "token"]
        response = requests.get(
            f'https://opentdb.com/api.php?amount={amount}&token={session_token}&encode=base64')
        data = response.json()['results']
    except requests.exceptions.RequestException:
        await ctx.respond("Something bad happened :pensive:", delete_after=10)
        return
    await ctx.respond(f"Succesfully loaded {amount} questions.", delete_after=10)
    for item in data:
        print(item)
        incorrect_answers = [base64.b64decode(i).decode() for i in item["incorrect_answers"]]
        item = {key: base64.b64decode(value).decode() for key, value in item.items() if
                key != "incorrect_answers"}
        item["incorrect_answers"] = incorrect_answers
        question = item['question']
        print(item)
        await ctx.send(f"""Category: "{item["category"]}"
Difficulty: {item["difficulty"]}
Question: {question}""", view=Trivia(item))


@bot.slash_command(name="cat")
async def cat(ctx, text: discord.Option(str, default="")):
    await ctx.defer()
    if text == "":
        await send_image(ctx, "https://cataas.com/cat", "cat.png")
    else:
        await send_image(ctx, f"https://cataas.com/cat/says/{text}", "cat.png")
    await ctx.delete()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")


bot.run(token)
