import discord
from redbot.core import commands, Config
from redbot.core.bot import Red
from redbot.core.commands import Context
from datetime import datetime, timedelta, timezone
from typing import Optional, Union, Dict
import asyncio
import logging
import re
import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Import utcnow properly
from discord.utils import utcnow

class AutoCleaner(commands.Cog):
    """Automatic message cleanup for specified channels with thread support"""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=867530912345, force_registration=True
        )
        
        default_guild = {
            "channels": {},  # {channel_id: {"days": 7, "enabled": False}}
            "log_channel": None,
            "schedule_time": None,  # "HH:MM" in local time or None (default 00:00)
            "timezone": "UTC"
        }
        
        self.config.register_guild(**default_guild)
        
        # Task tracker: guild_id -> task
        self.cleanup_tasks: Dict[int, asyncio.Task] = {}
        
        # Proper Red logging
        self.log = logging.getLogger("red.cogs.AutoCleaner")
        self.log.info("AutoCleaner cog initialized")

    async def cog_load(self):
        """Schedule cleanup tasks after bot is ready"""
        self.log.info("AutoCleaner: cog_load() triggered - scheduling tasks")
        self.bot.loop.create_task(self._delayed_startup())

    async def _delayed_startup(self):
        """Wait for bot to be ready, then schedule per-guild tasks"""
        try:
            await self.bot.wait_until_ready()
            for guild in self.bot.guilds:
                await self._schedule_guild_task(guild)
            self.log.info("AutoCleaner: All scheduled cleanup tasks started")
        except Exception as e:
            self.log.error("Failed to start scheduled tasks", exc_info=e)

    def cog_unload(self):
        """Cancel all tasks on unload"""
        for task in self.cleanup_tasks.values():
            if not task.done():
                task.cancel()
        self.cleanup_tasks.clear()
        self.log.info("AutoCleaner: All cleanup tasks cancelled on unload")

    async def red_delete_data_for_user(self, **kwargs):
        """Red-compliant data deletion handler"""
        return

    async def _schedule_guild_task(self, guild: discord.Guild):
        """Schedule or reschedule cleanup task for a guild"""
        guild_id = guild.id
        # Cancel existing
        if guild_id in self.cleanup_tasks:
            self.cleanup_tasks[guild_id].cancel()
            del self.cleanup_tasks[guild_id]

        # Always schedule - even if None, it uses default
        task = asyncio.create_task(self._scheduled_cleanup_task(guild))
        self.cleanup_tasks[guild_id] = task

    async def _get_next_run(self, guild: discord.Guild) -> datetime:
        """Calculate next cleanup time in UTC using system TZ (e.g. America/Los_Angeles)"""
        schedule_time = await self.config.guild(guild).schedule_time()
        time_str = schedule_time or "00:00"
        hh, mm = map(int, time_str.split(":"))

        # Use standard TZ env var with full IANA support
        tz_name = os.getenv("TZ", "UTC")
        try:
            local_tz = ZoneInfo(tz_name)
            self.log.info(f"Using timezone: {tz_name}")
        except ZoneInfoNotFoundError:
            self.log.warning(f"Invalid TZ='{tz_name}', falling back to UTC")
            local_tz = timezone.utc

        now = datetime.now(local_tz)
        target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)

        utc_time = target.astimezone(timezone.utc)
        self.log.info(f"Schedule: {time_str} {tz_name} -> Next run: {utc_time.strftime('%Y-%m-%d %H:%M UTC')}")
        return utc_time

    async def _scheduled_cleanup_task(self, guild: discord.Guild):
        """Run cleanup daily at scheduled time"""
        await self.bot.wait_until_ready()
        while True:
            try:
                next_run = await self._get_next_run(guild)
                delay = (next_run - datetime.now(timezone.utc)).total_seconds()
                
                # Ensure minimum delay of 60 seconds to prevent immediate cleanup on reload
                if delay < 60:
                    self.log.info(f"Calculated delay too short ({delay:.2f}s), adding 24h buffer for {guild.name}")
                    delay += 86400  # Add 24 hours
                
                schedule_time = await self.config.guild(guild).schedule_time() or "00:00"
                self.log.info(f"Next cleanup for {guild.name} in {delay/3600:.2f} hours at {schedule_time} local")
                await asyncio.sleep(delay)

                await self._clean_guild_channels(guild)
                self.log.info(f"Scheduled cleanup complete for {guild.name}")

            except asyncio.CancelledError:
                self.log.info(f"Scheduled cleanup task cancelled for {guild.name}")
                break
            except Exception as e:
                self.log.error(f"Error in scheduled cleanup for {guild.name}", exc_info=e)
                await asyncio.sleep(3600)

    async def _validate_channels(self, guild: discord.Guild) -> bool:
        """Remove deleted channels/threads from config"""
        async with self.config.guild(guild).channels() as channels:
            to_remove = []
            for channel_id in channels:
                channel = guild.get_channel(int(channel_id))
                thread = guild.get_thread(int(channel_id)) if not channel else None
                if (channel is None and thread is None) or \
                   (channel and channel.guild != guild) or \
                   (thread and thread.guild != guild):
                    to_remove.append(channel_id)
            for cid in to_remove:
                del channels[cid]
            return len(to_remove) > 0

    async def _get_log_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        channel_id = await self.config.guild(guild).log_channel()
        if not channel_id:
            return None
        channel = guild.get_channel(channel_id)
        if not channel:
            await self.config.guild(guild).log_channel.set(None)
            self.log.debug(f"Cleared invalid log channel {channel_id}")
        return channel

    async def _send_log(self, guild: discord.Guild, message: str = "", embed: Optional[discord.Embed] = None):
        log_channel = await self._get_log_channel(guild)
        if not log_channel:
            return
        try:
            if embed:
                await log_channel.send(embed=embed)
            else:
                await log_channel.send(message)
        except discord.Forbidden:
            self.log.warning(f"Missing permissions to send logs in {log_channel.name}")

    async def _clean_guild_channels(self, guild: discord.Guild):
        guild_config = await self.config.guild(guild).channels()
        cleaned = []
        
        for channel_id, settings in guild_config.items():
            if not settings.get("enabled", False):
                continue
                
            channel = guild.get_channel(int(channel_id))
            if not channel:
                channel = guild.get_thread(int(channel_id))
            if not channel:
                continue
                
            if not self._has_manage_messages_permission(channel):
                continue
                
            deleted = await self._clean_channel_safely(channel, settings["days"])
            if deleted > 0:
                cleaned.append((channel, deleted))
        
        if cleaned:
            await self._send_cleanup_summary(guild, cleaned)

    async def _send_cleanup_summary(self, guild: discord.Guild, cleaned_channels: list):
        embed = discord.Embed(
            title="Cleanup Summary",
            description=f"Completed at {utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            color=discord.Color.green()
        )
        for channel, count in cleaned_channels:
            # embed.add_field(name=f"#{channel.name}", value=f"Deleted {count} messages", inline=True)
            embed.add_field(name=f"{channel.mention}", value=f"Deleted {count} messages", inline=True)
        await self._send_log(guild, embed=embed)

    def _has_manage_messages_permission(self, channel: discord.abc.GuildChannel) -> bool:
        return channel.permissions_for(channel.guild.me).manage_messages

    async def _clean_channel_safely(self, channel: Union[discord.TextChannel, discord.Thread], days: int) -> int:
        try:
            cutoff = utcnow() - timedelta(days=days)
            if isinstance(channel, discord.Thread):
                deleted = await self._clean_thread(channel, cutoff)
            else:
                deleted = await self._clean_regular_channel(channel, cutoff)
            # == Suppress individual messages, send one embed instead. Uses Discord's autocomplete for channel/thread links ===
            # if deleted > 0:
                # await self._send_log(
                    # channel.guild,
                    # f"Cleaned {deleted} messages from {channel.mention} (older than {days} days)"
                # )
            return deleted
        except discord.Forbidden:
            await self._send_log(channel.guild, f"Missing permissions in {channel.mention}")
        except discord.HTTPException as e:
            await self._send_log(channel.guild, f"HTTP error in {channel.mention}: {e}")
        except Exception as e:
            await self._send_log(channel.guild, f"Error in {channel.mention}: {e}")
            self.log.error(f"Unexpected error cleaning {channel.name}", exc_info=True)
        return 0

    async def _clean_regular_channel(self, channel: discord.TextChannel, cutoff: datetime) -> int:
        most_recent = None
        async for msg in channel.history(limit=1):
            most_recent = msg
            break

        def check(m: discord.Message):
            if m.pinned: return False
            if most_recent and m.id == most_recent.id: return False
            return m.created_at < cutoff

        deleted = await channel.purge(limit=None, check=check, bulk=False, before=cutoff)
        return len(deleted)

    async def _clean_thread(self, thread: discord.Thread, cutoff: datetime) -> int:
        most_recent = None
        async for msg in thread.history(limit=1):
            most_recent = msg
            break

        starter_id = None
        try:
            starter = await thread.fetch_message(thread.id)
            starter_id = starter.id
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            try:
                async for msg in thread.history(limit=1, oldest_first=True):
                    starter_id = msg.id
                    break
            except (discord.NotFound, discord.HTTPException):
                pass

        def check(m: discord.Message):
            if m.pinned: return False
            if most_recent and m.id == most_recent.id: return False
            if starter_id and m.id == starter_id: return False
            return m.created_at < cutoff

        deleted = await thread.purge(limit=None, check=check, bulk=False, before=cutoff)
        return len(deleted)

    # ==================== COMMANDS ====================

    @commands.guild_only()
    @commands.group()
    @commands.admin_or_permissions(manage_guild=True)
    async def autoclean(self, ctx: Context):
        """Manage automatic message cleanup settings for channels and threads."""
        pass

    @autoclean.command(name="add")
    async def autoclean_add(self, ctx: Context, channel: Union[discord.TextChannel, discord.Thread] = None, days: int = 7):
        """Add a channel or thread to automatic cleanup."""
        if channel is None:
            channel = ctx.channel
        if channel.guild != ctx.guild:
            return await ctx.send("Channel must be in this server")
        if days < 1:
            return await ctx.send("Retention days must be at least 1")
        if not self._has_manage_messages_permission(channel):
            return await ctx.send("I need 'Manage Messages' permission in that channel")

        async with self.config.guild(ctx.guild).channels() as channels:
            channels[str(channel.id)] = {"days": days, "enabled": False}

        await ctx.send(
            f"Added {channel.mention} to auto-cleanup (keep {days} days)\n"
            f"To start use **{ctx.prefix}autoclean enable** {channel.mention}"
        )

    @autoclean.command(name="remove")
    async def autoclean_remove(self, ctx: Context, channel: Union[discord.TextChannel, discord.Thread] = None):
        """Remove a channel or thread from automatic cleanup."""
        if channel is None:
            channel = ctx.channel
        if channel.guild != ctx.guild:
            return await ctx.send("Channel must be in this server")

        async with self.config.guild(ctx.guild).channels() as channels:
            key = str(channel.id)
            if key in channels:
                del channels[key]
                await ctx.send(f"Removed {channel.mention} from auto-cleanup")
            else:
                await ctx.send(f"{channel.mention} is not configured")

    @autoclean.command(name="list")
    async def autoclean_list(self, ctx: Context):
        """List all configured channels with status and retention."""
        await self._validate_channels(ctx.guild)
        channels = await self.config.guild(ctx.guild).channels()
        if not channels:
            return await ctx.send("No channels configured")

        embed = discord.Embed(title="Auto-Cleanup Channels", color=await ctx.embed_color())
        for cid, settings in channels.items():
            ch = ctx.guild.get_channel(int(cid)) or ctx.guild.get_thread(int(cid))
            if ch:
                status = "Enabled" if settings["enabled"] else "Disabled"
                # Use channel mention instead of plain text name
                embed.add_field(
                    name=f"{status} - {ch.mention}", 
                    value=f"Keep {settings['days']} days", 
                    inline=False
                )
        await ctx.send(embed=embed)

    @autoclean.command(name="enable")
    async def autoclean_enable(self, ctx: Context, channel: Union[discord.TextChannel, discord.Thread] = None):
        """Enable auto-cleanup for a configured channel."""
        if channel is None:
            channel = ctx.channel
        if channel.guild != ctx.guild:
            return await ctx.send("Channel must be in this server")

        async with self.config.guild(ctx.guild).channels() as channels:
            key = str(channel.id)
            if key in channels:
                channels[key]["enabled"] = True
                await ctx.send(f"Enabled auto-cleanup for {channel.mention}")
            else:
                await ctx.send(f"Use `{ctx.prefix}autoclean add` first")

    @autoclean.command(name="disable")
    async def autoclean_disable(self, ctx: Context, channel: Union[discord.TextChannel, discord.Thread] = None):
        """Disable auto-cleanup for a configured channel."""
        if channel is None:
            channel = ctx.channel
        if channel.guild != ctx.guild:
            return await ctx.send("Channel must be in this server")

        async with self.config.guild(ctx.guild).channels() as channels:
            key = str(channel.id)
            if key in channels:
                channels[key]["enabled"] = False
                await ctx.send(f"Disabled auto-cleanup for {channel.mention}")
            else:
                await ctx.send(f"Not configured")
                
    @autoclean.command(name="keep")
    async def autoclean_keep(self, ctx: Context, channel: Union[discord.TextChannel, discord.Thread] = None, days: int = None):
        """Change how many days to keep for a configured channel or thread.
        
        Retention is calculated from the time the cleanup runs (not calendar midnight).
        For example, if the cog runs at 02:00, `keep 1` will keep roughly the last 26 hours.
        
        If no days value is given, shows the current retention setting.
        """
        if channel is None:
            channel = ctx.channel

        if channel.guild != ctx.guild:
            return await ctx.send("Channel must be in this server")

        async with self.config.guild(ctx.guild).channels() as channels:
            key = str(channel.id)
            if key not in channels:
                return await ctx.send(f"{channel.mention} is not configured. Use `{ctx.prefix}autoclean add` first.")

            if days is None:
                current = channels[key]["days"]
                await ctx.send(f"{channel.mention} currently keeps **{current}** days.")
                return

            if days < 1:
                return await ctx.send("Retention days must be at least 1.")

            old_days = channels[key]["days"]
            channels[key]["days"] = days
            await ctx.send(f"Updated {channel.mention}: Now keeping **{days}** days (was {old_days}).")                

    @autoclean.command(name="runnow")
    async def autoclean_runnow(self, ctx: Context):
        """Manually trigger cleanup for this guild."""
        await ctx.send("Running manual cleanup...")
        await self._clean_guild_channels(ctx.guild)
        await ctx.send("Manual cleanup complete.")

    @autoclean.group(name="schedule", invoke_without_command=True)
    async def autoclean_schedule(self, ctx: Context, time: str = None):
        """Set daily cleanup time (24-hour: HH:MM). Use `off` to reset to default (00:00 local)."""
        if time is None:
            await ctx.send_help()
            return

        if time.lower() == "off":
            await self.config.guild(ctx.guild).schedule_time.set(None)
            await self._schedule_guild_task(ctx.guild)
            await ctx.send("Cleanup schedule reset to **00:00** (local time, default)")
            return

        if not re.match(r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$", time):
            return await ctx.send("Invalid format. Use `HH:MM` (24-hour), e.g., `03:15` or `17:45`")

        await self.config.guild(ctx.guild).schedule_time.set(time)
        await self._schedule_guild_task(ctx.guild)
        
        await ctx.send(f"Cleanup scheduled daily at **{time}** (local time)")

    @autoclean_schedule.command(name="status")
    async def autoclean_schedule_status(self, ctx: Context):
        """Show current scheduled cleanup time."""
        schedule_time = await self.config.guild(ctx.guild).schedule_time()
        embed = discord.Embed(title="Cleanup Schedule", color=await ctx.embed_color())
        if schedule_time:
            embed.add_field(name="Time", value=f"**{schedule_time}** (local)", inline=False)
            embed.add_field(name="Status", value="Custom", inline=False)
        else:
            embed.add_field(name="Time", value="**00:00** (local)", inline=False)
            embed.add_field(name="Status", value="Default", inline=False)
        await ctx.send(embed=embed)

    @autoclean.group(name="logs", invoke_without_command=True)
    async def autoclean_logs(self, ctx: Context, channel: discord.TextChannel = None):
        """Set or disable log channel."""
        if channel:
            if channel.guild != ctx.guild:
                return await ctx.send("Channel must be in this server")
            perms = channel.permissions_for(ctx.guild.me)
            if not (perms.send_messages and perms.embed_links):
                return await ctx.send("I need Send Messages + Embed Links")
            await self.config.guild(ctx.guild).log_channel.set(channel.id)
            await ctx.send(f"Logs will be sent to {channel.mention}")
        else:
            await self.config.guild(ctx.guild).log_channel.set(None)
            await ctx.send("Logging disabled")

    @autoclean_logs.command(name="status")
    async def autoclean_logs_status(self, ctx: Context):
        """Show logging status."""
        log_channel = await self._get_log_channel(ctx.guild)
        embed = discord.Embed(title="Auto-Cleanup Logging", color=await ctx.embed_color())
        if log_channel:
            embed.add_field(name="Channel", value=log_channel.mention, inline=True)
            embed.add_field(name="Status", value="Enabled", inline=True)
        else:
            embed.add_field(name="Status", value="Disabled", inline=True)
            embed.description = f"Use `{ctx.prefix}autoclean logs #channel` to enable"
        await ctx.send(embed=embed)

    @autoclean.command(name="test")
    async def autoclean_test(self, ctx: Context):
        """Send test log message."""
        log_channel = await self._get_log_channel(ctx.guild)
        if not log_channel:
            return await ctx.send("Set a log channel first with `autoclean logs #channel`")
        embed = discord.Embed(
            title="Auto-Cleanup Test",
            description="Logging is working!",
            color=discord.Color.blue(),
            timestamp=utcnow()
        )
        embed.add_field(name="Tested By", value=ctx.author.display_name)
        await self._send_log(ctx.guild, embed=embed)
        await ctx.send(f"Test sent to {log_channel.mention}")

    @autoclean.command(name="cleanup")
    async def autoclean_cleanup(self, ctx: Context):
        """Remove invalid channels from config."""
        removed = await self._validate_channels(ctx.guild)
        if removed:
            await ctx.send("Removed deleted channels from config")
        else:
            await ctx.send("No deleted channels found")

async def setup(bot: Red):
    await bot.add_cog(AutoCleaner(bot))