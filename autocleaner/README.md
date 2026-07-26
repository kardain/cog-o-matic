# AutoCleaner for Red-DiscordBot

Automatic message cleanup for channels and threads. Set a retention period per channel, and AutoCleaner sweeps out anything older than that on a daily schedule. Pinned messages, the most recent message, and thread starter messages are always left alone.

## Features

* **Per-Channel Retention** - Configure a different retention period (in days) for each channel or thread.
* **Thread Support** - Works on both regular text channels and threads, correctly detecting and preserving the thread starter message.
* **Safe by Default** - Never deletes pinned messages, never deletes the most recent message in a channel (so a channel is never left completely empty), and skips channels the bot lacks `Manage Messages` in.
* **Handles Old Messages** - Uses single-message deletion rather than Discord's bulk-delete endpoint, so it isn't limited to messages under 14 days old. Larger cleanups will get rate-limited by Discord as a result, but Red/discord.py handle that automatically.
* **Scheduled Daily Cleanup** - Runs automatically once per day at a configurable time.
* **Optional Logging** - Point a log channel at it for a per-run summary embed showing what was cleaned where.
* **Multi-guild support** - All settings are per-server.
* **Manual Trigger** - Run a cleanup on demand without waiting for the schedule.

> **Note on scheduling:** the daily cleanup time is interpreted using the timezone of the machine/container the bot is running on (its `TZ` environment variable, defaulting to UTC if unset). Since one bot process serves every server it's in, this timezone is **shared across all guilds**. It isn't configurable per server, even though each server's actual cleanup *time* (`HH:MM`) is.

---

## Installation

### Prerequisites

This cog requires an active instance of Red-DiscordBot. If you don't have one set up yet:

* **Standalone Installation:** [Red-DiscordBot Installation Guide](https://github.com/cog-creators/red-discordbot#installation)
* **Docker Deployment:** [PhasecoreX Docker Red-DiscordBot](https://github.com/PhasecoreX/docker-red-discordbot)

The bot needs the following permissions in any channel you want AutoCleaner to manage:

* `View Channel`
* `Manage Messages`
* `Read Message History`

If you're using the logging feature, the bot also needs `Send Messages` and `Embed Links` in the log channel.

### Adding the Cog to Your Bot

```text
[p]repo add cogomatic https://github.com/kardain/cog-o-matic
[p]cog install cogomatic autocleaner
[p]load autocleaner
```

---

## Commands Reference

All `autoclean` commands require **Administrator** or **Manage Server** permissions.

* **`[p]autoclean add [channel] [days]`**
  Adds a channel or thread to auto-cleanup with the given retention period in days (default 7). Defaults to the current channel if none is given. Added channels start **disabled**. Use `enable` to activate.

* **`[p]autoclean remove [channel]`**
  Removes a channel or thread from auto-cleanup.

* **`[p]autoclean enable [channel]`**
  Enables cleanup for a channel already added via `add`.

* **`[p]autoclean disable [channel]`**
  Disables cleanup for a channel without removing its settings.

* **`[p]autoclean keep [channel] [days]`**
  Views or updates the retention period for a configured channel. Omit `days` to see the current setting. Retention is calculated from the time the cleanup actually runs, not calendar midnight. For example, a cleanup running at 02:00 with `keep 1` retains roughly the last 26 hours, not a strict calendar day.

* **`[p]autoclean list`**
  Lists all configured channels/threads with their enabled status and retention period.

* **`[p]autoclean runnow`**
  Manually triggers a cleanup pass immediately, without waiting for the daily schedule.

* **`[p]autoclean schedule <HH:MM|off>`**
  Sets the daily cleanup time (24-hour format). Use `off` to reset to the default of `00:00`. See the timezone note above regarding what "local" means here.

* **`[p]autoclean schedule status`**
  Shows the currently configured cleanup time.

* **`[p]autoclean logs [channel]`**
  Sets a channel to receive per-run cleanup summaries. Run with no channel to disable logging.

* **`[p]autoclean logs status`**
  Shows whether logging is enabled and which channel is set.

* **`[p]autoclean test`**
  Sends a test message to the configured log channel to confirm logging is working.

* **`[p]autoclean cleanup`**
  Scans the configured channel list and removes entries pointing to channels or threads that no longer exist. This cleans up the *configuration*, not messages. For that, see `runnow` or the daily schedule.)
