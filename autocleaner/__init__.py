from .autocleaner import AutoCleaner

__red_end_user_data_statement__ = (
    "This cog does not persistently store end user data. "
    "It only stores server configuration for auto-cleanup channels and log settings."
)

async def setup(bot):
    await bot.add_cog(AutoCleaner(bot))