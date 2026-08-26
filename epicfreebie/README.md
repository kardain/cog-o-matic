# EpicFreebie

Monitors and posts weekly free games from the Epic Games Store.

## Features

- **Direct API Tracking:** Utilizes Epic's direct production endpoint to pull listings seamlessly.
- **Discord Thread Support:** Fully supports posting directly into Discord Threads, Forum channels, and standard Text channels.
- **Duplicate Prevention:** Tracks previously notified items via a storage list to prevent duplicate messages.
- **Localization Config:** Allows custom locale and country configurations per server to catch regional promotions.
- **Ad-hoc Status Posting:** Includes manual admin check triggers to on-demand pull live promotion details.

---

## Installation

### Prerequisites

This cog requires an active instance of Red-DiscordBot. If you don't have one set up yet:

* **Standalone Installation:** [Red-DiscordBot Installation Guide](https://github.com/cog-creators/red-discordbot#installation)
* **Docker Deployment:** [PhasecoreX Docker Red-DiscordBot](https://github.com/PhasecoreX/docker-red-discordbot)

The bot needs the following permissions in the channel/thread where posts are to occur:

* `View Channel`
* `Manage Messages`
* `Read Message History`
* `Manage Messages and Threads`
* `Embed Links`
* `Send Messages and Create Posts`
* `Send Messages in Threads and Posts`

### Adding the Cog to Your Bot

```text
[p]repo add cogomatic https://github.com/kardain/cog-o-matic
[p]cog install cogomatic epicfreebie
[p]load epicfreebie
```
---

## Commands Reference

- `[p]epicset`  
Base command group for managing Epic Games browserless automation configurations.  
  - **User Permissions:** Admin or `Manage Guild`  

- `[p]epicset channel [target]`  
Configure alerts to fire directly into a target channel context or thread. If no channel is specified, defaults to the current channel.  
  - **Arguments:** `[target]` - A text channel, thread, or voice channel mention/ID.

- `[p]epicset clear`  
Deactivates the announcement task routine and completely removes configurations for the server.

- `[p]epicset region <locale> <country>`  
Modifies the regional storefront targeting criteria used when querying the Epic Games API payload.
  
  - Arguments:  
    - `<locale>`: Language/locale format string (e.g., `en-US`, `de`, `fr`).
    - `<country>`: Two-letter ISO country code (e.g., `US`, `DE`, `FR`).

- `[p]epicset showregion`  
Displays the currently active localization settings configured for the guild.

- `[p]epicset check`  
Forces an API check to pull and generate embeds of all live free games, skipping notification history filters.
