# 🌡️ Ecobee CLI (Unofficial)

A command-line interface to control your Ecobee thermostat.

Since Ecobee discontinued their public developer API, this CLI reverse-engineers their internal web API to give you command-line control of your thermostat.

## ✨ Features

- **One-time login** — Browser opens, you log in, session is saved
- **Auto token refresh** — Automatically refreshes expired tokens
- **Full control** — Status, temperature, modes, comfort settings
- **Celsius by default** — Perfect for 🇨🇦 users (Fahrenheit available with `-f`)

## ⚠️ Disclaimer

This is **unofficial** and uses Ecobee's internal API. It may break if Ecobee changes their web app. Use at your own risk. Not affiliated with Ecobee.

## 📦 Installation

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/ecobee-cli.git
cd ecobee-cli

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium

# Make executable (optional)
chmod +x ecobee.py

# Add to PATH (optional)
ln -s $(pwd)/ecobee.py ~/bin/ecobee
```

## 🚀 Quick Start

```bash
# One-time setup: login via browser
./ecobee.py login

# Now use the CLI anytime:
./ecobee.py status
```

## 📖 Commands

| Command | Description | Example |
|---------|-------------|---------|
| `login` | One-time browser login | `ecobee login` |
| `logout` | Clear saved credentials | `ecobee logout` |
| `status` | Show thermostat status | `ecobee status` |
| `set-temp` | Set temperature hold | `ecobee set-temp 22` |
| `set-mode` | Set HVAC mode | `ecobee set-mode heat` |
| `hold` | Set comfort setting | `ecobee hold home` |
| `resume` | Resume schedule | `ecobee resume` |
| `sensors` | Show sensor readings | `ecobee sensors` |

### Temperature

```bash
# Celsius (default)
ecobee set-temp 22

# Fahrenheit
ecobee set-temp 72 --fahrenheit
ecobee set-temp 72 -f

# Hold types
ecobee set-temp 22 --hold-type indefinite   # Until manually changed
ecobee set-temp 22 --hold-type nextTransition  # Until next schedule (default)
```

### Modes

```bash
ecobee set-mode heat        # Heating only
ecobee set-mode cool        # Cooling only
ecobee set-mode auto        # Auto heat/cool
ecobee set-mode off         # System off
ecobee set-mode auxheatonly # Aux/emergency heat
```

### Comfort Settings

```bash
ecobee hold home            # "Home" comfort setting
ecobee hold away            # "Away" comfort setting  
ecobee hold sleep           # "Sleep" comfort setting
```

## 🔐 How Authentication Works

1. **Login (one-time):** Opens a browser, you log in with your Ecobee credentials, the CLI captures the session cookies and JWT token

2. **Normal use:** CLI reads saved token and makes API calls directly

3. **Auto-refresh:** When token expires (~1 hour), CLI automatically gets a new one using the saved session (headless browser)

4. **Session expires:** You only need to re-login if you logout from ecobee.com or change your password

### Where Credentials Are Stored

```
~/.ecobee/
├── token.json      # Access token (auto-refreshes)
└── session.json    # Browser session for auto-refresh
```

Both files are stored with `600` permissions (owner read/write only).

## 🛠️ Troubleshooting

### "Token expired" + auto-refresh fails

Your Ecobee session was invalidated (logged out on web, password changed, etc.). Run `ecobee login` again.

### Browser doesn't open

Make sure Playwright and Chromium are installed:
```bash
pip install playwright
playwright install chromium
```

### API errors

Ecobee may have changed their internal API. Please [open an issue](../../issues).

## 🔍 Technical Details

### API Endpoints (Reverse Engineered)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/1/thermostat` | GET | Get thermostat data |
| `/1/thermostat` | POST | Control thermostat |
| `/1/thermostatSummary` | GET | Quick status |

### Authentication

- **Provider:** Auth0 via `auth.ecobee.com`
- **Token:** JWT Bearer token
- **Lifetime:** ~1 hour (auto-refreshes)

### Request Format

```http
GET https://api.ecobee.com/1/thermostat?format=json&json={...}&_timestamp=...
Authorization: Bearer <jwt_token>
Accept: application/json
Content-Type: application/json;charset=UTF-8
```

## 🤝 Contributing

Contributions welcome! Please feel free to submit a Pull Request.

## 📄 License

MIT License - see [LICENSE](LICENSE) file.

## 🙏 Acknowledgments

- Built with reverse-engineering and determination after Ecobee killed their public API
- Uses [Playwright](https://playwright.dev/) for browser automation
