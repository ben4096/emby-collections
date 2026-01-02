# Emby Collection Manager

Automatically create and sync Emby collections based on external movie lists from MDBList and Trakt.tv.

## Features

- **Multiple Sources**: Fetch lists from MDBList and Trakt.tv
- **Automatic Matching**: Match movies using IMDb ID, TMDb ID, or title
- **Smart Sync**: Add new items and optionally remove items no longer in lists
- **Seasonal Collections**: Show/hide collections based on date ranges
- **Custom Images**: Set custom collection posters
- **Dry Run Mode**: Test without making changes
- **Detailed Logging**: Track all operations
- **Unraid Support**: User Scripts integration with automated setup

## Requirements

- Python 3.7+
- Emby Server with API access
- API keys for MDBList and/or Trakt (depending on sources used)

## Installation

### Option 1: Unraid (Recommended for Unraid users)

See [UNRAID_INSTALL.md](UNRAID_INSTALL.md) for complete Unraid installation guide.

**Quick steps:**
1. Install Python 3 from Unraid Settings → Plugins
2. Install User Scripts plugin
3. Create a new user script named `emby-collections`
4. Copy content from [unraid_user_script.sh](unraid_user_script.sh)
5. Edit the `REPO_URL` variable to point to your fork
6. Run the script to initialize
7. Edit `/mnt/user/appdata/emby-collections/config.yaml` with your API keys
8. Run again and schedule it

### Option 2: Local/Server Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/emby.git
cd emby

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy example config
cp config.yaml.example config.yaml

# Edit config with your settings
nano config.yaml  # or your preferred editor
```

## Configuration

### Required Configuration

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

### Configure Collections

Edit the `collections` section in `config.yaml`:

```yaml
collections:
  # MDBList example
  - name: "Top Watched This Week"
    source: "mdblist"
    list_id: "linaspurinis/top-watched-movies-of-the-week"
    overview: "Most watched movies this week"

  # Seasonal collection with custom image
  - name: "Christmas Movies"
    source: "mdblist"
    list_id: "snoak/christmas-movies"
    image: "images/christmas-movies.jpeg"
    seasonal:
      start_month: 12
      start_day: 15
      end_month: 12
      end_day: 26

  # Trakt example
  - name: "Trending Movies"
    source: "trakt"
    category: "trending"  # Options: trending, popular, watched, played, anticipated
    limit: 50
    sort_by: "rating"  # Sort by rating, votes, or title
```

## Usage

### Command Line Options

```bash
python emby_collections.py [options]

Options:
  -c, --config PATH    Config file path (default: config.yaml)
  --dry-run            Don't actually modify collections
  --clear              Clear existing collections before syncing
  --delete-unlisted    Delete collections not in config (WARNING!)
```

### Running the Script

**Test with dry-run:**
```bash
python emby_collections.py --dry-run
```

**Run once:**
```bash
python emby_collections.py
```

**Clear and rebuild collections:**
```bash
python emby_collections.py --clear
```

## Scheduling

### Unraid (User Scripts)

1. Go to Settings → User Scripts
2. Select your `emby-collections` script
3. Click on **Schedule Disabled**
4. Choose frequency:
   - **Daily** at a specific time (e.g., 2 AM)
   - **Custom** cron expression

Example cron: `0 2 * * *` (daily at 2 AM)

### Linux/Mac (cron)

Add to crontab (`crontab -e`):

```bash
# Run daily at 2 AM
0 2 * * * cd /path/to/emby && /path/to/venv/bin/activate && python emby_collections.py
```

### Windows (Task Scheduler)

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (e.g., daily at 2 AM)
4. Action: Start a program
   - Program: `C:\path\to\venv\Scripts\python.exe`
   - Arguments: `emby_collections.py`
   - Start in: `C:\path\to\emby`

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
- `snoak/christmas-movies` - Christmas movies

Browse more at [mdblist.com](https://mdblist.com/)

## Trakt Lists

### Categories

Available Trakt categories:
- `trending` - Currently trending
- `popular` - Most popular overall
- `watched` - Most watched recently (weekly)
- `played` - Most played (by unique users, weekly)
- `anticipated` - Most anticipated upcoming
- `boxoffice` - Current box office

### User Lists

You can also fetch user-created lists:

```yaml
- name: "Custom List"
  source: "trakt"
  username: "someuser"
  list_slug: "list-name"
```

### Example

```yaml
- name: "Popular on Trakt"
  source: "trakt"
  category: "popular"
  limit: 100
  sort_by: "rating"
```

## Advanced Features

### Seasonal Collections

Collections can automatically appear/disappear based on dates:

```yaml
- name: "Halloween Collection"
  source: "mdblist"
  list_id: "halloween-movies"
  seasonal:
    start_month: 10  # October
    start_day: 1
    end_month: 10
    end_day: 31
```

Collections out of season are automatically hidden (but movies remain in library).

### Custom Images

Add custom collection posters:

```yaml
- name: "My Collection"
  source: "mdblist"
  list_id: "some-list"
  image: "images/my-poster.jpg"  # Relative to project root
```

Supported formats: JPG, PNG, JPEG

### Sorting

Sort movies within collections:

```yaml
- name: "Top Rated"
  source: "trakt"
  category: "popular"
  sort_by: "rating"  # Options: rating, votes, title
```

### Display Order

Control default sort field in Emby:

```yaml
- name: "My Collection"
  source: "mdblist"
  list_id: "some-list"
  display_order: "PremiereDate"  # or "SortName"
  sort_title: "01"  # Controls collection order in library
```

## Configuration Options

See [config.yaml.example](config.yaml.example) for all available options.

Key settings:

```yaml
settings:
  # Don't modify collections, just log what would happen
  dry_run: false

  # Clear collections before syncing
  clear_collections: false

  # Delete collections not in config
  delete_unlisted: false

  # Log level: DEBUG, INFO, WARNING, ERROR
  log_level: "INFO"

  # Matching priority (try in order)
  match_priority: ["imdb_id", "tmdb_id", "title"]

  # Remove items from collection if not in source list
  remove_missing: true
```

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
- Ensure Emby server is running and accessible

**MDBList/Trakt errors:**
- Verify API keys
- Check internet connection
- Some lists might be private or removed

### Duplicate Collections

The script searches for existing collections by exact name match. If you have duplicates:
1. Delete extras in Emby
2. Or rename in config to create new collection

### Unraid-Specific Issues

See [UNRAID_INSTALL.md](UNRAID_INSTALL.md) for Unraid-specific troubleshooting.

## Project Structure

```
emby/
├── emby_collections.py          # Main script
├── config.yaml                  # Your configuration (create from example)
├── config.yaml.example          # Configuration template
├── requirements.txt             # Python dependencies
├── README.md                    # This file
├── UNRAID_INSTALL.md           # Unraid installation guide
├── unraid_user_script.sh       # Unraid User Script
├── images/                      # Custom collection posters
└── src/
    ├── emby_client.py          # Emby API client
    ├── mdblist_fetcher.py      # MDBList fetcher
    ├── trakt_fetcher.py        # Trakt fetcher
    └── collection_manager.py   # Collection sync logic
```

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

View logs:
```bash
# Tail the log file
tail -f emby_collections.log

# Last 50 lines
tail -50 emby_collections.log
```

## License

MIT License - feel free to modify and use as needed.

## Contributing

Issues and pull requests welcome!

## Acknowledgments

- [Emby](https://emby.media/) - Media server
- [MDBList](https://mdblist.com/) - Movie lists and metadata
- [Trakt.tv](https://trakt.tv/) - Movie tracking and lists
