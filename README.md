# 🌡️ Ecobee CLI

**Control your Ecobee thermostat from your computer's command line.**

Ecobee stopped letting developers use their official API, so I made this tool that works around that limitation. It lets you check your thermostat status, change the temperature, and more — all from your terminal.

---

## What Can It Do?

- ✅ Check current temperature and settings
- ✅ Change the temperature
- ✅ Switch between Heat/Cool/Auto/Off modes
- ✅ Set Home/Away/Sleep comfort settings
- ✅ See all your sensor readings
- ✅ Resume your normal schedule

---

## Before You Start

You'll need:
1. **A Mac or Linux computer** (Windows may work but isn't tested)
2. **Python 3** installed (most Macs have this already)
3. **An Ecobee account** with a thermostat set up

---

## Installation (One-Time Setup)

### Step 1: Download the code

Open **Terminal** (on Mac: press `Cmd + Space`, type "Terminal", press Enter)

Then copy and paste these commands one at a time:

```bash
# Go to your home folder
cd ~

# Download the code
git clone https://github.com/sumesh2279/ecobee-cli.git

# Go into the folder
cd ecobee-cli
```

### Step 2: Install required software

```bash
# Install the browser automation tool
pip3 install playwright

# Download the browser it needs
playwright install chromium
```

### Step 3: Make it easy to run from anywhere

```bash
# Create a shortcut
mkdir -p ~/bin
ln -sf ~/ecobee-cli/ecobee.py ~/bin/ecobee

# Add the shortcut folder to your system (one-time)
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshrc

# Activate it
source ~/.zshrc
```

### Step 4: Log in to Ecobee (one-time)

```bash
ecobee login
```

This will:
1. Open a browser window
2. You log in with your normal Ecobee email and password
3. The tool saves your session (securely, only on your computer)

**That's it! You're set up.**

---

## How to Use It

Open Terminal and type any of these commands:

### Check your thermostat status
```bash
ecobee status
```
Shows: current temperature, humidity, what mode it's in, outside weather, and sensor readings.

### Change the temperature
```bash
# Set to 22 degrees Celsius
ecobee set-temp 22

# Set to 72 degrees Fahrenheit
ecobee set-temp 72 -f
```

### Change the mode
```bash
ecobee set-mode heat    # Heating only
ecobee set-mode cool    # Cooling only (AC)
ecobee set-mode auto    # Automatic (heat or cool as needed)
ecobee set-mode off     # Turn off
```

### Use comfort settings
```bash
ecobee hold home     # Use your "Home" settings
ecobee hold away     # Use your "Away" settings
ecobee hold sleep    # Use your "Sleep" settings
```

### Go back to your normal schedule
```bash
ecobee resume
```

### See all sensor temperatures
```bash
ecobee sensors
```

---

## Common Questions

### "It says my token expired"

Don't worry! The tool automatically refreshes it. If it can't, just run:
```bash
ecobee login
```

### "Command not found: ecobee"

Open a new Terminal window, or run:
```bash
source ~/.zshrc
```

### "I get an error about Playwright"

Run these commands:
```bash
pip3 install playwright
playwright install chromium
```

### "Is my password saved?"

**No.** The tool only saves a temporary session token (like how websites keep you logged in). Your password is never stored. The session files are saved in a hidden folder (`~/.ecobee/`) with secure permissions that only you can read.

### "Will this stop working?"

It might, if Ecobee changes their website significantly. If that happens, check back here for updates or open an issue on GitHub.

---

## Uninstalling

If you want to remove everything:

```bash
# Remove the program
rm -rf ~/ecobee-cli
rm ~/bin/ecobee

# Remove your saved login session
rm -rf ~/.ecobee
```

---

## For Developers

### How it works

1. Uses Playwright (browser automation) to log in to ecobee.com
2. Captures the authentication token from the browser session
3. Makes API calls to Ecobee's internal API (same one their website uses)
4. Auto-refreshes tokens when they expire using the saved browser session

### API Endpoints (reverse-engineered)

| Endpoint | Description |
|----------|-------------|
| `GET /1/thermostat` | Get thermostat data |
| `POST /1/thermostat` | Control thermostat |

### Contributing

Found a bug? Have an idea? Open an issue or pull request!

---

## License

MIT License — free to use, modify, and share.

---

## Disclaimer

This is an **unofficial** tool. It's not made by or affiliated with Ecobee. It works by using the same internal website API that ecobee.com uses, which means it could stop working if Ecobee changes their website. Use at your own risk!
