import discord
from redbot.core import commands, Config
from redbot.core.commands import Context
from discord.ext import tasks
from datetime import datetime, timezone, timedelta

class DistortionTracker(commands.Cog):
    """Tracks the hidden hourly Destiny 2 Distortion planet rotation."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=8923748923, force_registration=True)
        default_global = {"channel_id": None}
        self.config.register_global(**default_global)
        
        # Guard to prevent spamming duplicate hourly notifications
        self.last_posted_hour = None        
        
        self.ROTATION = [
                    "Moon", "Europa", "Nessus", "Cosmodrome", 
                    "EDZ", "Dreaming City", "Savathûn's Throne World"
                ]
                
        self.PLANET_DATA = {
                    "Moon": {
                        "image": "https://www.bungie.net/img/destiny_content/pgcr/patrol_moon.jpg",
                        "armor": "Dreambane",
                        "two_piece": "Nightmarish Power",
                        "four_piece": "Nightmarish Resilience",
                        "weapon_trait": "Loss",
                        "trait_desc": "This weapon gains bonus stability, handling, and aim assist whenever your shields are broken or when a friendly Guardian is defeated. Effect lasts until you are defeated.",
                        "link": "https://www.blueberries.gg/weapons/destiny-2-moon-weapons/",
                        "case_file": "https://www.sportskeeda.com/mmo/all-moon-luna-case-file-locations-destiny-2"
                    },
                    "Europa": {
                        "image": "https://www.bungie.net/img/destiny_content/pgcr/europa-mission-club.jpg",
                        "armor": "Crystoscrene",
                        "two_piece": "Resupply",
                        "four_piece": "From the Storm",
                        "weapon_trait": "Winterized Gear",
                        "trait_desc": "After being out of combat for a moderate duration, this weapon gains stability, reload speed, and handling. These benefits decay over time after reentering combat.",
                        "link": "https://www.blueberries.gg/weapons/europa-loot-pool/",
                        "case_file": "https://www.sportskeeda.com/mmo/all-europa-case-file-locations-destiny-2"
                    },
                    "Nessus": {
                        "image": "https://www.bungie.net/img/destiny_content/pgcr/patrol_nessus.jpg",
                        "armor": "Exodus Down",
                        "two_piece": "Emergency Electromagnet",
                        "four_piece": "Repurposed Charge",
                        "weapon_trait": "Fail-Deadly",
                        "trait_desc": "Dealing damage grants a stacking bonus to magazine size, target acquisition, and range until your next final blow with this weapon.",
                        "link": "https://www.blueberries.gg/weapons/nessus-loot-pool/",
                        "case_file": "https://www.sportskeeda.com/esports/all-nessus-case-file-locations-destiny-2"
                    },
                    "Cosmodrome": {
                        "image": "https://www.bungie.net/img/destiny_content/pgcr/cosmodrome-explore.jpg",
                        "armor": "Seventh Seraph",
                        "two_piece": "Rasputin's Wrath",
                        "four_piece": "Rasputin's Reprisal",
                        "weapon_trait": "Rasputin's Arsenal",
                        "trait_desc": "Breaking a target's shield partially reloads this weapon's magazine.",
                        "link": "https://www.blueberries.gg/weapons/cosmodrome-loot-pool/",
                        "case_file": "https://www.sportskeeda.com/mmo/all-cosmodrome-case-file-locations-destiny-2"
                    },
                    "EDZ": {
                        "image": "https://www.bungie.net/img/destiny_content/pgcr/patrol_edz.jpg",
                        "armor": "Wildwood",
                        "two_piece": "Watchtower",
                        "four_piece": "Field Expertise",
                        "weapon_trait": "Veteran's Wisdom",
                        "trait_desc": "Rapid or precision final blows release a Kinetic shockwave that exhausts targets.",
                        "link": "https://www.blueberries.gg/weapons/edz-loot-pool/",
                        "case_file": "https://www.sportskeeda.com/mmo/all-edz-case-file-locations-destiny-2"
                    },
                    "Dreaming City": {
                        "image": "https://www.bungie.net/img/destiny_content/pgcr/free_roam_dreaming_city.jpg",
                        "armor": "Reverie Dawn",
                        "two_piece": "A Wish for Protection",
                        "four_piece": "A Wish Fulfilled",
                        "weapon_trait": "Advanced Reflexes",
                        "trait_desc": "Upon taking damage from a target, quickly guard or aim down sights with this weapon to gain bonus damage, handling, and charge rate for a short time.",
                        "link": "https://www.blueberries.gg/weapons/dreaming-city-loot-pool/",
                        "case_file": "https://www.sportskeeda.com/mmo/all-dreaming-city-case-file-locations-destiny-2"
                    },
                    "Savathûn's Throne World": {
                        "image": "https://www.bungie.net/img/destiny_content/pgcr/throneworld_freeroam.jpg",
                        "armor": "Veritas",
                        "two_piece": "Lucent Transmutation",
                        "four_piece": "Lucent Tithes",
                        "weapon_trait": "Psychohack",
                        "trait_desc": "Sustained damage from this weapon exhausts the target for a short duration. Exhausted targets deal reduced outgoing damage.",
                        "link": "https://www.blueberries.gg/weapons/throne-world-loot-pool/",
                        "case_file": "https://www.sportskeeda.com/mmo/all-throne-world-case-file-locations-destiny-2"
                    },
                }        
        
        # ANCHOR corresponsds to Friday, July 3, 2026, at 12:00:00 PM UTC.
        self.CURRENT_ANCHOR = 495300
        self.auto_poster_loop.start()

    def cog_unload(self):
        self.auto_poster_loop.cancel()

    def get_planet_data(self):
        now = datetime.now(timezone.utc)
        this_hour = now.replace(minute=0, second=0, microsecond=0)
        current_hours = int(this_hour.timestamp() // 3600)
        
        rotation_index = ((current_hours - self.CURRENT_ANCHOR) + 1) % len(self.ROTATION)
        active_planet = self.ROTATION[rotation_index]
        
        next_hour = this_hour + timedelta(hours=1)
        next_hour_unix = int(next_hour.timestamp())
        
        return active_planet, next_hour_unix

    def build_embed(self, active_planet, next_change):
        data = self.PLANET_DATA.get(active_planet, {})
        thumbnail_url = data.get("image")
        armor_set = data.get("armor", "Unknown")
        two_piece = data.get("two_piece", "Unknown")
        four_piece = data.get("four_piece", "Unknown")
        weapon_trait = data.get("weapon_trait", "Unknown")
        trait_desc = data.get("trait_desc", "Unknown")
        link = data.get("link", "#")
        case_file = data.get("case_file", "#")

# Next appearance of current planet
# = next rotation + (number of planets - 1) hours
# Currently 7 planets so add 6 hours
# This comment block is intentionally not indented properly
        next_appearance = datetime.fromtimestamp(next_change, tz=timezone.utc) + timedelta(hours=6)
        next_appearance_unix = int(next_appearance.timestamp())
        
        rotation_index = self.ROTATION.index(active_planet)
        next_index = (rotation_index + 1) % len(self.ROTATION)
        next_planet = self.ROTATION[next_index]

        embed = discord.Embed(
            title=":milky_way: Distortion Event Tracker",
            description=(
                f"**Active Zone:** {active_planet}\n\n"
                f"**Featured Armor:** [{armor_set}]({link})\n"
                f"**Two Piece Set Perk:** {two_piece}\n"
                f"**Four Piece Set Perk:** {four_piece}\n\n"
                f"**Weapon Trait:** {weapon_trait}\n\n"
                f"Check armor link above for trait description + weapon loot pool\n\n"
                f"**Case Files:** [Click Here]({case_file}) - Text guide\n"
                f":warning: **Only obtainable when location is active**\n\n"
                f"**Next Distortion Appears:** <t:{next_change}:R> on {next_planet}\n\n"
                f"**{active_planet} appears next:** <t:{next_appearance_unix}:t> (<t:{next_appearance_unix}:R>)\n"
            ),
            color=discord.Color.red()
        )
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
        embed.set_footer(text="Rotates Hourly")
        return embed

    @commands.guild_only()
    @commands.group()
    @commands.admin_or_permissions(manage_channels=True)
    async def distortion(self, ctx: Context):
        """Manage the Destiny 2 Distortion tracker admin panel."""
        pass

    @distortion.command(name="set")
    async def distortion_set(self, ctx, channel: discord.TextChannel = None):
        """Set the channel for hourly automated posts."""
        target_channel = channel or ctx.channel
        await self.config.channel_id.set(target_channel.id)
        await ctx.send(f":white_check_mark: Hourly distortion tracker set to {target_channel.mention}")

    @distortion.command(name="clear")
    async def distortion_clear(self, ctx):
        """Clear the target channel and stop automated posts."""
        await self.config.channel_id.set(None)
        await ctx.send(":octagonal_sign: Hourly distortion posts have been stopped and cleared.")

    @distortion.command(name="force")
    async def distortion_force(self, ctx):
        """Force send the current distortion embed to the configured channel (for testing)."""
        channel_id = await self.config.channel_id()
        if not channel_id:
            await ctx.send(":x: No channel has been set for distortion posts. Use `[p]distortion set` first.")
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            await ctx.send(":x: Could not find the configured channel.")
            return

        active_planet, next_change = self.get_planet_data()
        embed = self.build_embed(active_planet, next_change)
        try:
            await channel.send(embed=embed)
            await ctx.send(f":white_check_mark: Force-sent distortion embed to {channel.mention}")
        except discord.Forbidden:
            await ctx.send(":x: Missing permissions to send messages in the configured channel.")
        except Exception as e:
            await ctx.send(f":x: Failed to send embed: {e}")
            
    @distortion.command(name="current")
    @commands.bot_has_permissions(send_messages=True)
    async def distortion_current(self, ctx: Context):
        """Check the active Distortion planet right now."""
        active_planet, next_change = self.get_planet_data()
        embed = self.build_embed(active_planet, next_change)
        await ctx.send(embed=embed)       

#TODO: Add cooldown and admin command to set cooldown time. Default cooldown to 5 seconds. Bot should not respond if on cooldown.        
            
    @tasks.loop(seconds=30)
    async def auto_poster_loop(self):
        """Background loop that executes exactly at the top of the hour."""
        channel_id = await self.config.channel_id()
        if not channel_id:
            return

        now = datetime.now(timezone.utc)
        current_hour_key = now.replace(minute=0, second=0, microsecond=0)

        if now.minute == 0 and (self.last_posted_hour is None or current_hour_key > self.last_posted_hour):
            channel = self.bot.get_channel(channel_id)
            if channel:
                active_planet, next_change = self.get_planet_data()
                embed = self.build_embed(active_planet, next_change)
                try:
                    await channel.send(embed=embed)
                    self.last_posted_hour = current_hour_key
                except discord.HTTPException:
                    pass
    
    @auto_poster_loop.before_loop
    async def before_auto_poster_loop(self):
        await self.bot.wait_until_ready()
