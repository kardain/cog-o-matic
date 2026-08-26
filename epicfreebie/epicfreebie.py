"""
MIT License

Copyright (c) 2024-present japandotorg

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import asyncio
from datetime import datetime, timezone
from urllib.parse import urlparse

import aiohttp
import discord
from redbot.core import Config, commands
from redbot.core.bot import Red

# Official free-games listing API? 
EPIC_FREEBIES_ENDPOINT = "https://store-site-backend-static-ipv4.ak.epicgames.com/freeGamesPromotions"

_INVALID_SLUG_CHARS = "[]{}<> "

__version__ = "0.99a"


class EpicFreebie(commands.Cog):
    """Monitors and posts weekly free games natively without browser dependencies."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=41002356, force_registration=True)
        default_guild = {
            "channel_id": None,
            "notified_ids": [],
            "locale": "en-US",
            "country": "US",
        }
        self.config.register_guild(**default_guild)
        self.check_loop = self.bot.loop.create_task(self._freebie_checker_loop())

    def cog_unload(self):
        self.check_loop.cancel()

    async def _fetch_epic_freebies(self, locale: str = "en-US", country: str = "US"):
        """Queries the Epic free games API directly using aiohttp."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": f"{locale},en;q=0.9",
        }
        params = {
            "locale": locale,
            "country": country,
            "allowCountries": country,
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    EPIC_FREEBIES_ENDPOINT, headers=headers, params=params, timeout=15
                ) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()
            except Exception:
                return []

        games = []
        try:
            elements = data["data"]["Catalog"]["searchStore"]["elements"]
        except (KeyError, TypeError):
            return []

        for game in elements:
            title = game.get("title", "Unknown Title")

            # Exclude game test bundles/vault slots that aren't real store offers
            if "test" in title.lower() or game.get("status") == "INACTIVE":
                continue

            promotions = game.get("promotions") or {}
            promo_offers = promotions.get("promotionalOffers", [])

            if promo_offers:
                for promo in promo_offers:
                    for offer in promo.get("promotionalOffers", []):
                        discount = offer.get("discountSetting", {})

                        # Match current free games
                        if discount.get("discountPercentage") == 0:
                            description = game.get("description", "No description available.")
                            game_id = game.get("id")
                            url = self._build_game_url(game)

                            thumbnail = None
                            for img in game.get("keyImages", []):
                                if img.get("type") in ["OfferImageWide", "Thumbnail", "DieselStoreFrontWide", "VaultClosed"]:
                                    thumbnail = img.get("url")
                                    break

                            end_date_str = offer.get("endDate")
                            end_date = None
                            if end_date_str:
                                end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))

                            games.append({
                                "id": game_id,
                                "title": title,
                                "description": description,
                                "url": url,
                                "thumbnail": thumbnail,
                                "end_date": end_date
                            })
        return games

    def _build_game_url(self, game) -> str:
        """Builds a safe store URL for a game, falling back to the homepage
        if the slug data from the API is missing or malformed."""
        page_slug = ""
        if game.get("productSlug"):
            page_slug = game["productSlug"]
        elif game.get("offerMappings"):
            page_slug = game["offerMappings"][0].get("pageSlug") or ""
        elif game.get("catalogNs", {}).get("mappings"):
            page_slug = game["catalogNs"]["mappings"][0].get("pageSlug") or ""

        if page_slug and all(c not in page_slug for c in _INVALID_SLUG_CHARS):
            candidate = f"https://store.epicgames.com/en-US/p/{page_slug.lstrip('/')}"
            parsed = urlparse(candidate)
            if parsed.scheme and parsed.netloc:
                return candidate

        return "https://store.epicgames.com/"

    async def _freebie_checker_loop(self):
        """Background loop checking the store every 60 minutes."""
        await self.bot.wait_until_ready()
        while True:
            try:
                for guild in self.bot.guilds:
                    channel_id = await self.config.guild(guild).channel_id()
                    if not channel_id:
                        continue

                    channel = guild.get_channel_or_thread(channel_id)
                    if not channel:
                        continue

                    locale = await self.config.guild(guild).locale()
                    country = await self.config.guild(guild).country()
                    games = await self._fetch_epic_freebies(locale=locale, country=country)
                    if not games:
                        continue

                    notified_ids = await self.config.guild(guild).notified_ids()
                    new_ids = []

                    for game in games:
                        if game["id"] not in notified_ids:
                            embed = self._build_game_embed(game)
                            try:
                                await channel.send(embed=embed)
                                new_ids.append(game["id"])
                            except discord.HTTPException:
                                pass

                    if new_ids:
                        updated_ids = (notified_ids + new_ids)[-30:]
                        await self.config.guild(guild).notified_ids.set(updated_ids)

            except Exception:
                pass

            await asyncio.sleep(3600)

    def _build_game_embed(self, game):
        """Helper to create consistent Discord embeds for games."""
        embed = discord.Embed(
            title=f"FREE on Epic Games: {game['title']}",
            description=game["description"],
            color=discord.Color.blue()
        )
        url = game.get("url") or ""
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            embed.url = url
        if game["thumbnail"]:
            embed.set_image(url=game["thumbnail"])
        if game["end_date"]:
            embed.add_field(
                name="Offer Ends",
                value=f"<t:{int(game['end_date'].timestamp())}:R>",
                inline=False
            )
        return embed

    # --- Commands ---

    @commands.group()
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def epicset(self, ctx: commands.Context):
        """Configuration commands for Epic Games free game alerts."""
        pass

    @epicset.command(name="channel")
    async def set_channel(self, ctx: commands.Context, target: discord.Thread | discord.TextChannel = None):
        """Set the channel or thread where free games are announced."""
        target = target or ctx.channel
        await self.config.guild(ctx.guild).channel_id.set(target.id)
        await ctx.send(f"Epic Games alerts configured for {target.mention}.")

    @epicset.command(name="clear")
    async def clear_channel(self, ctx: commands.Context):
        """Disable Epic Games alerts for this server."""
        await self.config.guild(ctx.guild).channel_id.set(None)
        await ctx.send("Epic Games alerts disabled.")

    @epicset.command(name="region")
    async def set_region(self, ctx: commands.Context, locale: str, country: str):
        """Set the locale and country used to query Epic's free games API.

        Example: `[p]epicset region en-US US` or `[p]epicset region de DE`

        `locale` is a language/locale code (e.g. en-US, de, fr, ja).
        `country` is a two-letter ISO country code (e.g. US, DE, FR, JP).
        This affects which free games and language show up, since Epic's
        promotions can vary slightly by region.
        """
        country = country.upper()
        if len(country) != 2 or not country.isalpha():
            await ctx.send("Country must be a two-letter code, e.g. `US`, `DE`, `FR`.")
            return

        await self.config.guild(ctx.guild).locale.set(locale)
        await self.config.guild(ctx.guild).country.set(country)
        await ctx.send(f"Epic Games alerts will now use locale `{locale}` and country `{country}`.")

    @epicset.command(name="showregion")
    async def show_region(self, ctx: commands.Context):
        """Show the currently configured locale/country for this server."""
        locale = await self.config.guild(ctx.guild).locale()
        country = await self.config.guild(ctx.guild).country()
        await ctx.send(f"Current settings: locale `{locale}`, country `{country}`.")

    @epicset.command(name="check")
    async def force_check(self, ctx: commands.Context):
        """Force an immediate check and show currently active free games."""
        locale = await self.config.guild(ctx.guild).locale()
        country = await self.config.guild(ctx.guild).country()

        async with ctx.typing():
            games = await self._fetch_epic_freebies(locale=locale, country=country)

        if not games:
            await ctx.send("No active free games found on the Epic Games Store right now.")
            return

        await ctx.send("### Currently Active Free Games:")
        for game in games:
            embed = self._build_game_embed(game)
            await ctx.send(embed=embed)
            
    @epicset.command(name="version", hidden=True)
    async def _rss_version(self, ctx):
        """Show the current version."""
        await ctx.send(f"Version {__version__}")            