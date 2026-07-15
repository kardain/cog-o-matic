# Distortion Tracker for Red-DiscordBot

A clean, mobile-optimized Red-DiscordBot cog that tracks the hidden hourly Destiny 2 Distortion planet rotation. It utilizes dynamic, native Discord timestamps to provide live countdown tracking without spamming API calls.

## Features
* **Automated Hourly Alerts:** Automatically posts the current rotation details directly to a configured channel at the top of every hour.
* **Smart Anti-Spam Filtering:** Features built-in drift protection and internal deduplication locks to ensure your channels never receive double posts.
* **Dynamic Timezones:** Uses native Discord relative time formatting (`<t:TIMESTAMP:R>`) so players see real-time countdowns tailored to their individual local device clocks.

---

## Installation

### Prerequisites
This cog requires an active instance of Red-DiscordBot. If you do not have one set up yet, follow one of the guides below:
* **Standalone Installation:** [Red-DiscordBot Installation Guide](https://github.com/cog-creators/red-discordbot#installation)
* **Docker Deployment:** [PhasecoreX Docker Red-DiscordBot](https://github.com/PhasecoreX/docker-red-discordbot)

### Adding the Cog to Your Bot
Open your Discord client and run the following commands in a channel your bot can read:

1. **Add the repository:**
   ```text
   [p]repo add distortion-tracker https://github.com/USER/REPO
   ```

2. **Install the cog package:**
   ```text
   [p]cog install distortion-tracker distortiontracker
   ```

3. **Load the cog into memory:**
   ```text
   [p]load distortiontracker
   ```

---

## Commands Reference

The main administrative commands require **Administrator** or **Manage Channels** permissions.

* **`[p]distortion`**  
  Displays the interactive help and module management menu.
  
* **`[p]distortion set [channel]`**  
  Registers a target text channel for the automated, hourly planet rotation alerts. If no channel is specified, it defaults to the channel where the command was run.
  
* **`[p]distortion clear`**  
  Deregisters the configured channel from automated posting and completely halts background tracking tasks.
  
* **`[p]distortion force`**  
  Bypasses timers to immediately force-send the active distortion embed. Perfect for manual testing or verifying layout details.

The following user commands are available and require **Send Messages** permissions in the desired channel(s):

* **`[p]distortion current`**  
  Displays the current planet in rotation, in the channel where the command is invoked. This command has a default 5 second cooldown.

---

## Previews

### Help Menu Panel (Old Version)
![Help Menu](help_panel.png)

### Active Distortion Embed
![Sample Embed](sample_embed.png)
