import asyncio
import logging
import math
from typing import List, Tuple

import discord
import lavalink
from fuzzywuzzy import process

from redbot.core import commands
from redbot.core.utils.chat_formatting import bold, humanize_number

from ...audio_dataclasses import LocalPath, Query
from ..abc import MixinMeta
from ..cog_utils import CompositeMetaClass, _

log = logging.getLogger("red.cogs.Audio.cog.Utilities.queue")


class QueueUtilities(MixinMeta, metaclass=CompositeMetaClass):
    async def _build_queue_page(
        self,
        ctx: commands.Context,
        queue: list,
        player: lavalink.player_manager.Player,
        page_num: int,
    ) -> discord.Embed:
        shuffle = await self.config.guild(ctx.guild).shuffle()
        repeat = await self.config.guild(ctx.guild).repeat()
        autoplay = await self.config.guild(ctx.guild).auto_play()

        queue_num_pages = math.ceil(len(queue) / 10)
        queue_idx_start = (page_num - 1) * 10
        queue_idx_end = queue_idx_start + 10
        if len(player.queue) > 500:
            queue_list = "__Too many songs in the queue, only showing the first 500__.\n\n"
        else:
            queue_list = ""

        arrow = await self.draw_time(ctx)
        pos = lavalink.utils.format_time(player.position)

        if player.current.is_stream:
            dur = "LIVE"
        else:
            dur = lavalink.utils.format_time(player.current.length)

        query = Query.process_input(player.current, self.local_folder_current_path)

        if query.is_stream:
            queue_list += _("**Currently livestreaming:**\n")
            queue_list += "**[{current.title}]({current.uri})**\n".format(current=player.current)
            queue_list += _("Requested by: **{user}**").format(user=player.current.requester)
            queue_list += f"\n\n{arrow}`{pos}`/`{dur}`\n\n"

        elif query.is_local:
            if player.current.title != "Unknown title":
                queue_list += "\n".join(
                    (
                        _("Playing: ")
                        + "**{current.author} - {current.title}**".format(current=player.current),
                        LocalPath(
                            player.current.uri, self.local_folder_current_path
                        ).to_string_user(),
                        _("Requested by: **{user}**\n").format(user=player.current.requester),
                        f"{arrow}`{pos}`/`{dur}`\n\n",
                    )
                )
            else:
                queue_list += "\n".join(
                    (
                        _("Playing: ")
                        + LocalPath(
                            player.current.uri, self.local_folder_current_path
                        ).to_string_user(),
                        _("Requested by: **{user}**\n").format(user=player.current.requester),
                        f"{arrow}`{pos}`/`{dur}`\n\n",
                    )
                )
        else:
            queue_list += _("Playing: ")
            queue_list += "**[{current.title}]({current.uri})**\n".format(current=player.current)
            queue_list += _("Requested by: **{user}**").format(user=player.current.requester)
            queue_list += f"\n\n{arrow}`{pos}`/`{dur}`\n\n"

        for i, track in enumerate(queue[queue_idx_start:queue_idx_end], start=queue_idx_start):
            if i % 100 == 0:  # TODO: Improve when Toby menu's are merged
                await asyncio.sleep(0.1)

            if len(track.title) > 40:
                track_title = str(track.title).replace("[", "")
                track_title = "{}...".format((track_title[:40]).rstrip(" "))
            else:
                track_title = track.title
            req_user = track.requester
            track_idx = i + 1
            query = Query.process_input(track, self.local_folder_current_path)

            if query.is_local:
                if track.title == "Unknown title":
                    queue_list += f"`{track_idx}.` " + ", ".join(
                        (
                            bold(
                                LocalPath(
                                    track.uri, self.local_folder_current_path
                                ).to_string_user()
                            ),
                            _("requested by **{user}**\n").format(user=req_user),
                        )
                    )
                else:
                    queue_list += f"`{track_idx}.` **{track.author} - {track_title}**, " + _(
                        "requested by **{user}**\n"
                    ).format(user=req_user)
            else:
                queue_list += f"`{track_idx}.` **[{track_title}]({track.uri})**, "
                queue_list += _("requested by **{user}**\n").format(user=req_user)
            await asyncio.sleep(0)

        embed = discord.Embed(
            colour=await ctx.embed_colour(),
            title="Queue for __{guild.name}__".format(guild=ctx.guild),
            description=queue_list,
        )
        if await self.config.guild(ctx.guild).thumbnail() and player.current.thumbnail:
            embed.set_thumbnail(url=player.current.thumbnail)
        queue_dur = await self.queue_duration(ctx)
        queue_total_duration = lavalink.utils.format_time(queue_dur)
        text = _(
            "Page {page_num}/{total_pages} | {num_tracks} tracks, {num_remaining} remaining\n"
        ).format(
            page_num=humanize_number(page_num),
            total_pages=humanize_number(queue_num_pages),
            num_tracks=len(player.queue),
            num_remaining=queue_total_duration,
        )
        text += (
            _("Auto-Play")
            + ": "
            + ("\N{WHITE HEAVY CHECK MARK}" if autoplay else "\N{CROSS MARK}")
        )
        text += (
            (" | " if text else "")
            + _("Shuffle")
            + ": "
            + ("\N{WHITE HEAVY CHECK MARK}" if shuffle else "\N{CROSS MARK}")
        )
        text += (
            (" | " if text else "")
            + _("Repeat")
            + ": "
            + ("\N{WHITE HEAVY CHECK MARK}" if repeat else "\N{CROSS MARK}")
        )
        embed.set_footer(text=text)
        return embed

    async def _build_queue_search_list(
        self, queue_list: List[lavalink.Track], search_words: str
    ) -> List[Tuple[int, str]]:
        track_list = []
        queue_idx = 0
        for i, track in enumerate(queue_list, start=1):
            if i % 100 == 0:  # TODO: Improve when Toby menu's are merged
                await asyncio.sleep(0.1)
            queue_idx = queue_idx + 1
            if not self.match_url(track.uri):
                query = Query.process_input(track, self.local_folder_current_path)
                if (
                    query.is_local
                    and query.local_track_path is not None
                    and track.title == "Unknown title"
                ):
                    track_title = query.local_track_path.to_string_user()
                else:
                    track_title = "{} - {}".format(track.author, track.title)
            else:
                track_title = track.title

            song_info = {str(queue_idx): track_title}
            track_list.append(song_info)
            await asyncio.sleep(0)
        search_results = process.extract(search_words, track_list, limit=50)
        search_list = []
        for search, percent_match in search_results:
            for queue_position, title in search.items():
                if percent_match > 89:
                    search_list.append((queue_position, title))
        return search_list

    async def _build_queue_search_page(
        self, ctx: commands.Context, page_num: int, search_list: List[Tuple[int, str]]
    ) -> discord.Embed:
        search_num_pages = math.ceil(len(search_list) / 10)
        search_idx_start = (page_num - 1) * 10
        search_idx_end = search_idx_start + 10
        track_match = ""
        for i, track in enumerate(
            search_list[search_idx_start:search_idx_end], start=search_idx_start
        ):
            if i % 100 == 0:  # TODO: Improve when Toby menu's are merged
                await asyncio.sleep(0.1)
            track_idx = i + 1
            if type(track) is str:
                track_location = LocalPath(track, self.local_folder_current_path).to_string_user()
                track_match += "`{}.` **{}**\n".format(track_idx, track_location)
            else:
                track_match += "`{}.` **{}**\n".format(track[0], track[1])
            await asyncio.sleep(0)
        embed = discord.Embed(
            colour=await ctx.embed_colour(), title=_("Matching Tracks:"), description=track_match
        )
        embed.set_footer(
            text=(_("Page {page_num}/{total_pages}") + " | {num_tracks} tracks").format(
                page_num=humanize_number(page_num),
                total_pages=humanize_number(search_num_pages),
                num_tracks=len(search_list),
            )
        )
        return embed