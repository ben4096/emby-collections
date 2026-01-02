# Unraid Installation Guide

This guide explains how to install and configure Emby Collections Sync on Unraid using a User Script.

## Prerequisites

1. **Python 3** must be installed on Unraid
   - Go to **Settings** → **Plugins** → search for "Python"
   - Or install via **NerdTools** or **Community Applications**
   - Verify installation with `python3 --version`

2. **User Scripts Plugin**
   - Install from Community Applications if not already installed
   - Search for "User Scripts" by Andrew Zawadzki

3. **Git** (usually already installed on Unraid)

## Installation

### Method 1: Automatic Installation with Script

1. **Create a new User Script**
   - Go to **Settings** → **User Scripts**
   - Click **Add New Script**
   - Name it `emby-collections`

2. **Copy the script**
   - Edit the script you just created
   - Copy the content from `unraid_user_script.sh` into the editor
   - The default repo URL is already configured, no changes needed

3. **Save the script**
   - Click **Save**
   - The script is automatically executable

4. **First run**
   - Click **Run Script**
   - The script will:
     - Clone the repository
     - Create a Python virtual environment
     - Install dependencies
     - Create a `config.yaml` file from example

5. **Configure your config file**
   - Edit `/mnt/user/appdata/emby-collections/config.yaml`
   - Add your Emby, MDBList, Trakt API keys
   - Configure your collections

6. **Run the script again**
   - Go back to User Scripts
   - Click **Run Script** to launch the first sync

### Method 2: Manual Installation

```bash
# Connect to Unraid via SSH

# Create installation directory
mkdir -p /mnt/user/appdata/emby-collections
cd /mnt/user/appdata/emby-collections

# Clone the repository
git clone https://github.com/ben4096/emby-collections.git .

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create your config (working example or blank template)
cp config.yaml.example config.yaml  # Recommended: working example
# OR: cp config.yaml.template config.yaml  # Blank template
nano config.yaml  # Edit with your settings

# Manual test
python emby_collections.py

# Deactivate environment
deactivate
```

## Scheduling

Once everything works:

1. Go to **Settings** → **User Scripts**
2. Find your `emby-collections` script
3. Click **Schedule Disabled**
4. Choose a frequency:
   - **Daily**: Once per day at midnight
   - **Hourly**: Every hour
   - **Custom**: Custom cron expression (recommended for specific times)

### Custom Cron Examples

To run every day at 2 AM:
```
0 2 * * *
```

To run every 6 hours:
```
0 */6 * * *
```

To run every Sunday at 4 AM:
```
0 4 * * 0
```

## File Structure

After installation, here's the structure in `/mnt/user/appdata/emby-collections/`:

```
emby-collections/
├── venv/                      # Python virtual environment (auto-created)
├── src/                       # Source code
├── emby_collections.py        # Main script
├── config.yaml               # Your configuration
├── requirements.txt          # Python dependencies
└── emby_collections.log      # Log file
```

## Viewing Logs

To see logs from your last execution:

```bash
tail -f /mnt/user/appdata/emby-collections/emby_collections.log
```

Or from User Scripts, click the log button for your script (may show "UNDEFINED" due to UI bug, but logs are written to file).

View last 50 lines:
```bash
tail -50 /mnt/user/appdata/emby-collections/emby_collections.log
```

## Updates

The script auto-updates on each run via `git pull`.

To force an update:
```bash
cd /mnt/user/appdata/emby-collections
git pull
source venv/bin/activate
pip install -r requirements.txt --upgrade
deactivate
```

## Troubleshooting

### Python 3 not found
```bash
# Check where Python 3 is located
which python3

# If different from /usr/bin/python3, modify PYTHON_BIN in the script
```

### venv module error
```bash
# Python 3 is minimal, install the full package from NerdTools
```

### Permission denied
```bash
# Make the script executable
chmod +x /boot/config/plugins/user.scripts/scripts/emby-collections/script
```

### Emby connection error
- Verify Emby URL in `config.yaml`
- Verify API key is correct
- Ensure Emby is accessible from Unraid

### Repository not found (private repo)
- Make sure your repository is public on GitHub
- Or configure git credentials for private repos

## Manual Testing

To test manually without User Scripts:

```bash
cd /mnt/user/appdata/emby-collections
source venv/bin/activate
python emby_collections.py --dry-run
deactivate
```

The `--dry-run` option allows testing without modifying Emby.

## Uninstallation

```bash
# Delete the User Script from the web interface
# Then delete the files
rm -rf /mnt/user/appdata/emby-collections
```
