import os
import asyncio

import async_timeout
import discord
from discord.ext import commands
from wavelink import Player
from discord.ui import Button, View

from .errors import InvalidLoopMode, NotEnoughSong, NothingIsPlaying


class CatPlayer(Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.queue = asyncio.Queue()
        self.loop = "NONE"  # CURRENT, PLAYLIST
        self.bound_channel = None
        self.track_provider = "yt"

    async def destroy(self) -> None:
        self.queue = None

        await super().stop()
        await super().disconnect()

    async def do_next(self) -> None:
        if self.is_playing():
            return

        timeout = int(os.getenv("CATMUSIC_TIMEOUT", 300))

        try:
            with async_timeout.timeout(timeout):
                track = await self.queue.get()
        except asyncio.TimeoutError:
            if not self.is_playing():
                await self.destroy()

            return

        self._source = track
        await self.play(track)
        self.client.dispatch("catmusic_track_start", self, track)
        await self.invoke_player()

    async def set_loop(self, loop_type: str) -> None:
        valid_types = ["NONE", "CURRENT", "PLAYLIST"]

        if not self.is_playing():
            raise NothingIsPlaying("Player is not playing any track. Can't loop")

        if not loop_type:
            if valid_types.index(self.loop) >= 2:
                loop_type = "NONE"
            else:
                loop_type = valid_types[valid_types.index(self.loop) + 1]

            if loop_type == "PLAYLIST" and len(self.queue._queue) < 1:
                loop_type = "NONE"

        if loop_type.upper() == "PLAYLIST" and len(self.queue._queue) < 1:
            raise NotEnoughSong(
                "There must be 2 songs in the queue in order to use the PLAYLIST loop")

        if loop_type.upper() not in valid_types:
            raise InvalidLoopMode("Loop type must be `NONE`, `CURRENT` or `PLAYLIST`.")

        self.loop = loop_type.upper()

        return self.loop

    async def invoke_player(self, ctx: commands.Context = None) -> None:
        track = self.source

        if not track:
            raise NothingIsPlaying("Player is not playing anything.")

        embed = discord.Embed(title=track.title, url=track.uri, color=discord.Color.blurple())
        embed.set_author(name=track.author, url=track.uri,
                         icon_url=self.client.user.display_avatar.url)
        try:
            embed.set_thumbnail(url=track.thumb)
        except AttributeError:
            pass
        embed.add_field(
            name="Length",
            value=f"{int(track.length // 60)}:{int(track.length % 60)}",
        )
        embed.add_field(name="Looping", value=self.loop)
        embed.add_field(name="Volume", value=self.volume)

        view = View()
        next_song = ""

        if self.loop == "CURRENT":
            next_song = self.source.title
        else:
            if len(self.queue._queue) > 0:
                next_song = self.queue._queue[0].title

        if next_song:
            embed.add_field(name="Next Song", value=next_song, inline=False)

        if not ctx:
            return await self.bound_channel.send(embed=embed, view=view)

        await ctx.respond(embed=embed, view=view)
