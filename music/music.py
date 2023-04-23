import asyncio
import async_timeout
import wavelink
import discord
from discord import ClientException, Color, Embed
from discord.commands import (
    slash_command,
)
from discord.ext import commands
from wavelink import LavalinkException, LoadTrackError, SoundCloudTrack, YouTubeMusicTrack, \
    YouTubeTrack
from wavelink.ext import spotify
from wavelink.ext.spotify import SpotifyTrack

from .checks import voice_channel_player, voice_connected
from .errors import MustBeSameChannel
from .player import CatPlayer

from typing import Union
from wavelink import SoundCloudTrack, YouTubeMusicTrack, YouTubeTrack
from wavelink.ext.spotify import SpotifyTrack

Provider = Union[YouTubeTrack, YouTubeMusicTrack, SoundCloudTrack, SpotifyTrack]


class Music(commands.Cog):
    """Music commands"""

    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.bot.loop.create_task(self.start_nodes())

    async def play_track(self, ctx: commands.Context, query: str, provider=None):
        player: CatPlayer = ctx.voice_client

        if ctx.author.voice.channel.id != player.channel.id:
            raise MustBeSameChannel("**You must be in the same voice channel as the player.**")

        track_provider = {
            "yt": YouTubeTrack,
            "ytmusic": YouTubeMusicTrack,
            "soundcloud": SoundCloudTrack,
            "spotify": SpotifyTrack,
        }

        msg = await ctx.respond(f"**Searching for** `{query}` :mag_right:")

        provider: Provider = (
            track_provider.get(provider) if provider else track_provider.get(player.track_provider)
        )
        nodes = wavelink.NodePool._nodes.values()

        for node in nodes:
            tracks = []
            try:
                async with async_timeout.timeout(20):
                    tracks = await provider.search(query, node=node)
                    break
            except asyncio.TimeoutError:
                self.bot.dispatch("catmusic_node_fail", node)
                continue
            except (LavalinkException, LoadTrackError):
                continue

        if not tracks:
            return await ctx.send("**No song/track found with given query.**")

        track = tracks[0]

        await ctx.send(f"**Added** `{track.title}` **to queue.** ")
        await player.queue.put(track)

        if not player.is_playing():
            await player.do_next()

    async def start_nodes(self):
        await self.bot.wait_until_ready()
        spotify_credential = getattr(self.bot, "spotify_credentials",
                                     {"client_id": "", "client_secret": ""})

        for config in self.bot.lavalink_nodes:
            try:
                node: wavelink.Node = await wavelink.NodePool.create_node(
                    bot=self.bot, **config,
                    spotify_client=spotify.SpotifyClient(**spotify_credential)
                )
                print(f"[music-cord] INFO - Created node: {node.identifier}")
            except Exception:
                print(
                    f"[music-cord] ERROR - Failed to create node {config['host']}:{config['port']}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.id == self.bot.user.id and before.channel is not None and after.channel is None:
            player: CatPlayer = next(
                i for i in self.bot.voice_clients if i.channel == before.channel)

            await player.destroy()
            self.bot.dispatch("catmusic_player_stop", player)

    @slash_command(aliases=["con"])
    @voice_connected()
    async def connect(self, ctx: commands.Context):
        """Connect the player"""
        if ctx.voice_client:
            return

        msg = await ctx.respond(f"**Connecting to **`{ctx.author.voice.channel}`")

        try:
            player: CatPlayer = await ctx.author.voice.channel.connect(cls=CatPlayer)
            self.bot.dispatch("catmusic_player_connect", player)
        except (asyncio.TimeoutError, ClientException):
            await ctx.send("**Failed to connect to voice channel.**")

        player.bound_channel = ctx.channel
        player.bot = self.bot

        await msg.edit_original_response(content=f"**Connected to **`{player.channel.name}`")

    @slash_command()
    async def music(self, ctx):
        em = discord.Embed(title="Music Commands",
                           description="`play` , `pause` , `resume`, `skip` , `seek` , `connect` , `volume` , `loop` , `queue` , `nowplaying` , alwaysjoined , `music`",
                           color=discord.Color.blurple())
        em.set_footer(text="Music Cord")
        await ctx.respond(embed=em)

    @slash_command(aliases=["vol"])
    @voice_channel_player()
    async def volume(self, ctx: commands.Context, vol: int, forced=False):
        """Set volume"""
        player: CatPlayer = ctx.voice_client

        if vol < 0:
            return await ctx.respond("**Volume can't be less than 0**")

        if vol > 100 and not forced:
            return await ctx.respond("**Volume can't greater than 100**")

        await player.set_volume(vol)
        await ctx.respond(f"**Volume set to** {vol} :loud_sound:")

    @slash_command(aliases=["p"], invoke_without_command=True)
    @voice_connected()
    async def play(self, ctx: commands.Context, *, query: str):
        """Play or add song to queue (Defaults to YouTube)"""
        await ctx.invoke(self.connect)
        await self.play_track(ctx, query)

    @slash_command(aliases=["disconnect", "dc"])
    @voice_channel_player()
    async def stop(self, ctx: commands.Context):
        """Stop the player"""
        player: CatPlayer = ctx.voice_client

        await player.destroy()
        await ctx.respond("**Stopped the player** :stop_button: ")
        self.bot.dispatch("catmusic_player_stop", player)

    @slash_command()
    @voice_channel_player()
    async def pause(self, ctx: commands.Context):
        """Pause the player"""
        player: CatPlayer = ctx.voice_client

        if player.is_playing():
            if player.is_paused():
                return await ctx.respond("**Player is already paused**.")

            await player.set_pause(pause=True)
            self.bot.dispatch("catmusic_player_pause", player)
            return await ctx.respond("**Paused** :pause_button: ")

        await ctx.respond("**Player is not playing anything.**")

    @slash_command()
    @voice_channel_player()
    async def resume(self, ctx: commands.Context):
        """Resume the player"""
        player: CatPlayer = ctx.voice_client

        if player.is_playing():
            if not player.is_paused():
                return await ctx.respond("**Player is already playing.**")

            await player.set_pause(pause=False)
            self.bot.dispatch("catmusic_player_resume", player)
            return await ctx.respond("**Resumed** :musical_note: ")

        await ctx.respond("**Player is not playing anything.**")

    @slash_command()
    @voice_channel_player()
    async def skip(self, ctx: commands.Context):
        """Skip to next song in the queue."""
        player: CatPlayer = ctx.voice_client

        if player.loop == "CURRENT":
            player.loop = "NONE"

        await player.stop()

        self.bot.dispatch("catmusic_track_skip", player)
        await ctx.respond("**Skipped** :track_next:")

    @slash_command()
    @voice_channel_player()
    async def seek(self, ctx: commands.Context, seconds: int):
        """Seek the player backward or forward"""
        player: CatPlayer = ctx.voice_client

        if player.is_playing():
            old_position = player.position
            position = old_position + seconds
            if position > player.source.length:
                return await ctx.respond("**Can't seek past the end of the track.**")

            if position < 0:
                position = 0

            await player.seek(position * 1000)
            self.bot.dispatch("catmusic_player_seek", player, old_position, position)
            return await ctx.respond(f"**Seeked {seconds} seconds** :fast_forward: ")

        await ctx.respond("**Player is not playing anything.**")

    @slash_command()
    @voice_channel_player()
    async def loop(self, ctx: commands.Context, loop_type: str = None):
        """Set loop to `NONE`, `CURRENT` or `PLAYLIST`"""
        player: CatPlayer = ctx.voice_client

        result = await player.set_loop(loop_type)
        await ctx.respond(f"Loop has been set to {result} :repeat: ")

    @slash_command(aliases=["q"])
    @voice_channel_player()
    async def queue(self, ctx: commands.Context):
        """Player queue"""
        player: CatPlayer = ctx.voice_client

        if len(player.queue._queue) < 1:
            return await ctx.respond("**Nothing is in the queue.**")

        embed = Embed(color=Color(0x2F3136))
        embed.set_author(
            name="Queue",
            icon_url="https://cdn.discordapp.com/attachments/776345413132877854/940247400046542948/list.png",
        )

        tracks = ""
        length = 0

        if player.loop == "CURRENT":
            next_song = f"Next > [{player.source.title}]({player.source.uri}) \n\n"
        else:
            next_song = ""

        if next_song:
            tracks += next_song

        for index, track in enumerate(player.queue._queue):
            tracks += f"{index + 1}. [{track.title}]({track.uri}) \n"
            length += track.length

        embed.description = tracks

        if length > 3600:
            length = f"{int(length // 3600)}h {int(length % 3600 // 60)}m {int(length % 60)}s"
        elif length > 60:
            length = f"{int(length // 60)}m {int(length % 60)}s"
        else:
            length = f"{int(length)}s"

        embed.set_footer(text=length)

        await ctx.respond(embed=embed)

    @slash_command(aliases=["np"])
    @voice_channel_player()
    async def nowplaying(self, ctx: commands.Context):
        """Currently playing song information"""
        player: CatPlayer = ctx.voice_client
        await player.invoke_player(ctx)
