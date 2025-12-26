# Emby Collection Manager

Automatically create and sync Emby collections based on external movie lists from MDBList and Trakt.tv.

## Features

- **Multiple Sources**: Fetch lists from MDBList and Trakt.tv
- **Automatic Matching**: Match movies using IMDb ID, TMDb ID, or title
- **Smart Sync**: Add new items and optionally remove items no longer in lists
- **Scheduled Updates**: Run daily or on-demand
- **Dry Run Mode**: Test without making changes
- **Detailed Logging**: Track all operations

## Requirements

- Python 3.7+
- Emby Server with API access
- API keys for MDBList and/or Trakt (depending on sources used)

## Quick Start

### 1. Installation

```bash
# Clone or download this repository
cd emby

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy example config
cp config.yaml.example config.yaml

# Edit config with your settings
nano config.yaml  # or your preferred editor
```

#### Required Configuration

**Emby Server:**
1. Get your Emby API key:
   - Open Emby web interface
   - Go to Dashboard → Advanced → Security → API Keys
   - Create a new API key
2. Add to `config.yaml`:
   ```yaml
   emby:
     url: "http://your-emby-server:8096"
     api_key: "your_api_key_here"
   ```

**MDBList (optional):**
1. Get API key from [MDBList Preferences](https://mdblist.com/preferences/)
2. Add to config:
   ```yaml
   mdblist:
     api_key: "your_mdblist_api_key"
   ```

**Trakt (optional):**
1. Create app at [Trakt API Apps](https://trakt.tv/oauth/applications)
2. Get Client ID
3. Add to config:
   ```yaml
   trakt:
     client_id: "your_trakt_client_id"
   ```

### 3. Configure Collections

Edit the `collections` section in `config.yaml`:

```yaml
collections:
  # MDBList example
  - name: "Top Watched This Week"
    source: "mdblist"
    list_id: "linaspurinis/top-watched-movies-of-the-week"

  # Trakt example
  - name: "Trending Movies"
    source: "trakt"
    category: "trending"  # Options: trending, popular, watched, played, anticipated
    limit: 50
```

### 4. Run

**Test with dry-run:**
```bash
python emby_collections.py --once --dry-run
```

**Run once:**
```bash
python emby_collections.py --once
```

**Run with scheduler (daily at configured time):**
```bash
python emby_collections.py
```

## Usage

### Command Line Options

```bash
python emby_collections.py [options]

Options:
  -c, --config PATH    Config file path (default: config.yaml)
  --once               Run once and exit (no scheduling)
  --dry-run            Don't actually modify collections
```

### Configuration Options

See [config.yaml.example](config.yaml.example) for all available options.

Key settings:

```yaml
settings:
  # Don't modify collections, just log what would happen
  dry_run: false

  # Log level: DEBUG, INFO, WARNING, ERROR
  log_level: "INFO"

  # Matching priority (try in order)
  match_priority: ["imdb_id", "tmdb_id", "title"]

  # Remove items from collection if not in source list
  remove_missing: true

  # Time to run daily sync (24h format)
  schedule_time: "02:00"
```

## MDBList Lists

### Finding List IDs

From a MDBList URL like:
```
https://mdblist.com/lists/linaspurinis/top-watched-movies-of-the-week
```

The `list_id` is: `linaspurinis/top-watched-movies-of-the-week`

### Popular Lists

Some useful MDBList IDs:
- `top-rated-movies` - IMDb Top 250
- `linaspurinis/top-watched-movies-of-the-week` - Weekly trending

Browse more at [mdblist.com](https://mdblist.com/)

## Trakt Lists

### Categories

Available Trakt categories:
- `trending` - Currently trending
- `popular` - Most popular overall
- `watched` - Most watched recently
- `played` - Most played (by unique users)
- `anticipated` - Most anticipated upcoming
- `boxoffice` - Current box office

### Example

```yaml
- name: "Popular on Trakt"
  source: "trakt"
  category: "popular"
  limit: 100
```

## Scheduling

### Linux/Mac (cron)

Add to crontab (`crontab -e`):

```bash
# Run daily at 2 AM
0 2 * * * cd /path/to/emby && /path/to/venv/bin/python emby_collections.py --once
```

### Windows (Task Scheduler)

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (e.g., daily at 2 AM)
4. Action: Start a program
   - Program: `C:\path\to\venv\Scripts\python.exe`
   - Arguments: `emby_collections.py --once`
   - Start in: `C:\path\to\emby`

### Using Built-in Scheduler

Run without `--once` flag:

```bash
python emby_collections.py
```

This will:
1. Run immediately on startup
2. Schedule daily runs at configured time
3. Keep running in background

Consider running in screen/tmux or as a service.

## Troubleshooting

### "No movies matched in library"

**Possible causes:**
1. Movies not in your Emby library
2. Missing external IDs (IMDb/TMDb) in Emby metadata
3. Different matching needed

**Solutions:**
- Refresh metadata in Emby
- Try different `match_priority` in config
- Use `--dry-run` to see detailed matching logs
- Check logs for specific movies not found

### Connection Errors

**Emby connection failed:**
- Verify URL and port
- Check API key is valid
- Ensure Emby server is running

**MDBList/Trakt errors:**
- Verify API keys
- Check internet connection
- Some lists might be private or removed

### Duplicate Collections

The script searches for existing collections by exact name match. If you have duplicates:
1. Delete extras in Emby
2. Or rename in config to create new collection

## Project Structure

```
emby/
├── emby_collections.py          # Main script
├── config.yaml                   # Your configuration (create from example)
├── config.yaml.example           # Configuration template
├── requirements.txt              # Python dependencies
├── README.md                     # This file
└── src/
    ├── emby_client.py           # Emby API client
    ├── mdblist_fetcher.py       # MDBList fetcher
    ├── trakt_fetcher.py         # Trakt fetcher
    └── collection_manager.py    # Collection sync logic
```

## Advanced Usage

### Custom Matching

Edit `match_priority` to change matching strategy:

```yaml
settings:
  # Try title first (less accurate but more matches)
  match_priority: ["title", "imdb_id", "tmdb_id"]
```

### Keep Manual Additions

Set `remove_missing: false` to never remove items:

```yaml
settings:
  remove_missing: false
```

This way you can manually add movies and they won't be removed.

### Multiple Configs

Run different configs for different purposes:

```bash
python emby_collections.py -c config-weekly.yaml --once
python emby_collections.py -c config-classics.yaml --once
```

## Future Enhancements (Plugin Version)

If this script works well, we can create an Emby plugin with:
- Built-in scheduling (no external cron needed)
- Configuration UI in Emby dashboard
- Native performance
- Better integration

## Logging

Logs are written to:
- Console (stdout)
- File: `emby_collections.log` (configurable)

Log levels: DEBUG, INFO, WARNING, ERROR

Change in config:
```yaml
settings:
  log_level: "DEBUG"  # More verbose
```

## License

MIT License - feel free to modify and use as needed.

## Contributing

Issues and pull requests welcome!

## Acknowledgments

- [Emby](https://emby.media/) - Media server
- [MDBList](https://mdblist.com/) - Movie lists and metadata
- [Trakt.tv](https://trakt.tv/) - Movie tracking and lists
