#!/usr/bin/env python3
"""
Ecobee CLI - Unofficial CLI for Ecobee Thermostats
Since Ecobee killed their public API, this uses their internal web API.

Usage:
    ecobee login           # Login via browser (one-time setup)
    ecobee status          # Show thermostat status
    ecobee set-temp <temp> # Set temperature (hold)
    ecobee set-mode <mode> # Set system mode (heat/cool/auto/off)
    ecobee resume          # Resume scheduled program
    ecobee sensors         # Show sensor readings

Token auto-refreshes using saved browser session. You only need to login once!
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

# File locations
DATA_DIR = Path.home() / ".ecobee"
TOKEN_FILE = DATA_DIR / "token.json"
SESSION_FILE = DATA_DIR / "session.json"  # Saved browser session

API_BASE = "https://api.ecobee.com"

# Auth0 configuration (from Ecobee's web app)
AUTH_CONFIG = {
    "domain": "auth.ecobee.com",
    "client_id": "183eORFPlXyz9BbDZwqexHPBQoVjgadh",
    "audience": "https://prod.ecobee.com/api/v1",
    "scope": "openid piiRead piiWrite smartRead smartWrite deleteGrants"
}


def ensure_data_dir():
    """Create data directory if needed."""
    DATA_DIR.mkdir(mode=0o700, exist_ok=True)


def load_token():
    """Load token from file."""
    if TOKEN_FILE.exists():
        try:
            data = json.loads(TOKEN_FILE.read_text())
            # Check if expired (with 5 min buffer)
            if data.get("expires_at", 0) > time.time() + 300:
                return data
            # Token expired, try to refresh
            print("⏳ Token expired, refreshing...")
            new_token = refresh_token()
            if new_token:
                return new_token
            print("⚠️  Could not refresh token, please login again")
        except Exception as e:
            print(f"Error loading token: {e}")
    return None


def save_token(token_data):
    """Save token to file."""
    ensure_data_dir()
    TOKEN_FILE.write_text(json.dumps(token_data, indent=2))
    TOKEN_FILE.chmod(0o600)


def save_session(cookies, storage_state=None):
    """Save browser session for auto-refresh."""
    ensure_data_dir()
    session_data = {
        "cookies": cookies,
        "storage_state": storage_state,
        "saved_at": time.time()
    }
    SESSION_FILE.write_text(json.dumps(session_data, indent=2))
    SESSION_FILE.chmod(0o600)


def load_session():
    """Load saved browser session."""
    if SESSION_FILE.exists():
        try:
            return json.loads(SESSION_FILE.read_text())
        except Exception:
            pass
    return None


def refresh_token():
    """Refresh token using saved browser session (headless)."""
    session = load_session()
    if not session:
        print("   No saved session found")
        return None
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("   Playwright not installed")
        return None
    
    print("   Using saved session to refresh...")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            
            # Restore cookies
            if session.get("cookies"):
                context.add_cookies(session["cookies"])
            
            page = context.new_page()
            
            # Navigate to portal - the cookies should auto-login
            page.goto("https://www.ecobee.com/consumerportal/", wait_until="networkidle", timeout=30000)
            
            # Wait a moment for any redirects/token refresh
            time.sleep(3)
            
            # Check for new token in cookies
            cookies = context.cookies()
            token = None
            thermostat_id = None
            
            for cookie in cookies:
                if cookie["name"] == "_TOKEN":
                    token = cookie["value"]
                    break
            
            if not token:
                # Maybe we got redirected to login
                if "login" in page.url.lower() or "auth" in page.url.lower():
                    print("   Session expired, need to login again")
                    browser.close()
                    return None
                
                # Try waiting a bit more
                time.sleep(5)
                cookies = context.cookies()
                for cookie in cookies:
                    if cookie["name"] == "_TOKEN":
                        token = cookie["value"]
                        break
            
            if token:
                # Save updated session
                save_session(cookies)
                
                # Extract thermostat ID from URL if available
                url = page.url
                if "/thermostats/" in url:
                    parts = url.split("/thermostats/")
                    if len(parts) > 1:
                        thermostat_id = parts[1].split("/")[0].split("?")[0]
                
                browser.close()
                
                # Decode token
                payload_b64 = token.split(".")[1]
                payload_b64 += "=" * (4 - len(payload_b64) % 4)
                payload = json.loads(base64.urlsafe_b64decode(payload_b64))
                
                # Load existing token data to preserve thermostat_id
                old_data = {}
                if TOKEN_FILE.exists():
                    try:
                        old_data = json.loads(TOKEN_FILE.read_text())
                    except:
                        pass
                
                token_data = {
                    "access_token": token,
                    "expires_at": payload.get("exp", time.time() + 3600),
                    "account_id": payload.get("https://claims.ecobee.com/ecobee_account_id"),
                    "thermostat_id": thermostat_id or old_data.get("thermostat_id")
                }
                
                save_token(token_data)
                print("   ✅ Token refreshed!")
                return token_data
            
            browser.close()
            print("   Could not get new token")
            return None
            
    except Exception as e:
        print(f"   Refresh failed: {e}")
        return None


def api_request(endpoint, method="GET", params=None, body=None, token=None):
    """Make an API request to Ecobee."""
    if token is None:
        token_data = load_token()
        if not token_data:
            print("❌ Not logged in. Run: ecobee login")
            sys.exit(1)
        token = token_data["access_token"]
    
    url = f"{API_BASE}{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json;charset=UTF-8",
        "Authorization": f"Bearer {token}"
    }
    
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        print(f"❌ API Error {e.code}: {error_body}")
        if e.code == 401:
            print("   Token may be invalid. Run: ecobee login")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Request failed: {e}")
        sys.exit(1)


def get_thermostat_id():
    """Get the thermostat ID."""
    token_data = load_token()
    if token_data and token_data.get("thermostat_id"):
        return token_data["thermostat_id"]
    
    # Try to get from thermostat list
    selection = {
        "selection": {
            "selectionType": "registered",
            "selectionMatch": "",
            "includeRuntime": False
        }
    }
    
    params = {
        "format": "json",
        "json": json.dumps(selection),
        "_timestamp": int(time.time() * 1000)
    }
    
    result = api_request("/1/thermostat", params=params)
    thermostats = result.get("thermostatList", [])
    
    if not thermostats:
        print("❌ No thermostats found")
        sys.exit(1)
    
    thermostat_id = thermostats[0].get("identifier")
    
    # Save for later
    if token_data:
        token_data["thermostat_id"] = thermostat_id
        save_token(token_data)
    
    return thermostat_id


def cmd_login(args):
    """Login via browser automation and save session."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ Playwright not installed. Run:")
        print("   pip install playwright")
        print("   playwright install chromium")
        sys.exit(1)
    
    ensure_data_dir()
    
    print("🌐 Opening browser for Ecobee login...")
    print("   Please log in with your Ecobee credentials.")
    print("   (This is a one-time setup - your session will be saved)")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        # Navigate to Ecobee portal
        page.goto("https://www.ecobee.com/consumerportal/")
        
        print("\n⏳ Waiting for login to complete...")
        print("   (The browser will close automatically when done)")
        
        # Wait for successful login (token appears in cookies)
        token = None
        thermostat_id = None
        
        for i in range(180):  # Wait up to 3 minutes
            time.sleep(1)
            
            # Check for token
            cookies = context.cookies()
            for cookie in cookies:
                if cookie["name"] == "_TOKEN":
                    token = cookie["value"]
                    break
            
            if token:
                # Wait a bit more for page to fully load
                time.sleep(2)
                
                # Try to extract thermostat ID from URL
                url = page.url
                if "/thermostats/" in url:
                    parts = url.split("/thermostats/")
                    if len(parts) > 1:
                        thermostat_id = parts[1].split("/")[0].split("?")[0]
                
                # Get final cookies
                cookies = context.cookies()
                break
            
            # Show progress
            if i > 0 and i % 30 == 0:
                print(f"   Still waiting... ({i}s)")
        
        if not token:
            browser.close()
            print("\n❌ Login failed or timed out")
            print("   Please try again and make sure to complete the login.")
            sys.exit(1)
        
        # Save session for future auto-refresh
        save_session(cookies)
        
        browser.close()
        
        # Decode token to get expiry
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        
        token_data = {
            "access_token": token,
            "expires_at": payload.get("exp", time.time() + 3600),
            "account_id": payload.get("https://claims.ecobee.com/ecobee_account_id"),
            "thermostat_id": thermostat_id
        }
        
        save_token(token_data)
        
        print("\n✅ Login successful!")
        print(f"   Session saved to: {SESSION_FILE}")
        print(f"   Token saved to: {TOKEN_FILE}")
        if thermostat_id:
            print(f"   Thermostat ID: {thermostat_id}")
        print("\n   Your session is saved - the CLI will auto-refresh tokens!")
        print("   You should only need to login again if you logout on the web.")


def f_to_c(f):
    """Convert Fahrenheit to Celsius."""
    return (f - 32) * 5 / 9


def c_to_f(c):
    """Convert Celsius to Fahrenheit."""
    return c * 9 / 5 + 32


def cmd_status(args):
    """Show thermostat status."""
    thermostat_id = get_thermostat_id()
    
    selection = {
        "selection": {
            "selectionType": "thermostats",
            "selectionMatch": thermostat_id,
            "includeRuntime": True,
            "includeSettings": True,
            "includeWeather": True,
            "includeSensors": True,
            "includeEquipmentStatus": True,
            "includeEvents": True
        }
    }
    
    params = {
        "format": "json",
        "json": json.dumps(selection),
        "_timestamp": int(time.time() * 1000)
    }
    
    result = api_request("/1/thermostat", params=params)
    
    if result.get("status", {}).get("code") != 0:
        print(f"❌ Error: {result}")
        sys.exit(1)
    
    thermostat = result.get("thermostatList", [{}])[0]
    runtime = thermostat.get("runtime", {})
    settings = thermostat.get("settings", {})
    weather = thermostat.get("weather", {}).get("forecasts", [{}])[0]
    events = thermostat.get("events", [])
    
    # Temperature is in tenths of degrees Fahrenheit
    current_temp_f = runtime.get("actualTemperature", 0) / 10.0
    desired_heat_f = runtime.get("desiredHeat", 0) / 10.0
    desired_cool_f = runtime.get("desiredCool", 0) / 10.0
    humidity = runtime.get("actualHumidity", 0)
    
    # Convert to Celsius for display
    current_temp_c = f_to_c(current_temp_f)
    desired_heat_c = f_to_c(desired_heat_f)
    desired_cool_c = f_to_c(desired_cool_f)
    
    hvac_mode = settings.get("hvacMode", "unknown")
    
    # Check for active holds
    active_hold = None
    for event in events:
        if event.get("running", False) and event.get("type") == "hold":
            active_hold = event
            break
    
    print("\n🌡️  ECOBEE STATUS")
    print("=" * 40)
    print(f"📍 Name:        {thermostat.get('name', 'Unknown')}")
    print(f"🌡️  Current:     {current_temp_c:.1f}°C ({current_temp_f:.1f}°F)")
    print(f"💧 Humidity:    {humidity}%")
    print(f"🔥 Heat Set:    {desired_heat_c:.1f}°C ({desired_heat_f:.1f}°F)")
    print(f"❄️  Cool Set:    {desired_cool_c:.1f}°C ({desired_cool_f:.1f}°F)")
    print(f"⚙️  Mode:        {hvac_mode}")
    
    if active_hold:
        hold_end = active_hold.get("endDate", "") + " " + active_hold.get("endTime", "")
        print(f"✋ Hold:        Active (until {hold_end})")
    
    # Weather
    outside_temp_f = weather.get("temperature", 0) / 10.0
    outside_temp_c = f_to_c(outside_temp_f)
    print(f"🌤️  Outside:     {outside_temp_c:.0f}°C ({outside_temp_f:.0f}°F), {weather.get('condition', 'Unknown')}")
    
    # Equipment status
    equipment = thermostat.get("equipmentStatus", "")
    if equipment:
        print(f"🔧 Running:     {equipment}")
    else:
        print(f"🔧 Running:     (idle)")
    
    # Sensors summary
    sensors = thermostat.get("remoteSensors", [])
    if sensors:
        print("\n📡 SENSORS")
        print("-" * 40)
        for sensor in sensors:
            name = sensor.get("name", "Unknown")
            caps = {c["type"]: c["value"] for c in sensor.get("capability", [])}
            temp_f = float(caps.get("temperature", 0)) / 10.0 if "temperature" in caps else None
            occupancy = caps.get("occupancy", "unknown")
            
            if temp_f:
                temp_c = f_to_c(temp_f)
                temp_str = f"{temp_c:.1f}°C ({temp_f:.1f}°F)"
            else:
                temp_str = "N/A"
            occ_str = "🟢" if occupancy == "true" else "⚪"
            print(f"  {name}: {temp_str} {occ_str}")


def cmd_set_temp(args):
    """Set temperature hold."""
    thermostat_id = get_thermostat_id()
    
    temp = float(args.temperature)
    temp_c = temp  # Store original for display
    
    # Default is Celsius, convert to Fahrenheit for API
    if args.fahrenheit:
        temp_f = temp
        temp_c = f_to_c(temp)
    else:
        # Input is Celsius, convert to Fahrenheit for API
        temp_f = c_to_f(temp)
    
    # Ecobee uses tenths of degrees Fahrenheit
    temp_int = int(temp_f * 10)
    
    hold_type = args.hold_type or "nextTransition"
    
    # For heat/cool spread
    heat_temp = temp_int
    cool_temp = temp_int + 40  # 4 degrees F higher for cool
    
    body = {
        "selection": {
            "selectionType": "thermostats",
            "selectionMatch": thermostat_id
        },
        "functions": [{
            "type": "setHold",
            "params": {
                "holdType": hold_type,
                "heatHoldTemp": heat_temp,
                "coolHoldTemp": cool_temp
            }
        }]
    }
    
    params = {"format": "json"}
    result = api_request("/1/thermostat", method="POST", params=params, body=body)
    
    if result.get("status", {}).get("code") == 0:
        print(f"✅ Temperature set to {temp_c:.1f}°C ({temp_f:.1f}°F)")
        print(f"   Hold type: {hold_type}")
    else:
        print(f"❌ Error: {result}")


def cmd_set_mode(args):
    """Set HVAC mode."""
    thermostat_id = get_thermostat_id()
    
    mode = args.mode.lower()
    valid_modes = ["heat", "cool", "auto", "off", "auxheatonly"]
    
    if mode not in valid_modes:
        print(f"❌ Invalid mode. Choose from: {', '.join(valid_modes)}")
        sys.exit(1)
    
    body = {
        "selection": {
            "selectionType": "thermostats",
            "selectionMatch": thermostat_id
        },
        "thermostat": {
            "settings": {
                "hvacMode": mode
            }
        }
    }
    
    params = {"format": "json"}
    result = api_request("/1/thermostat", method="POST", params=params, body=body)
    
    if result.get("status", {}).get("code") == 0:
        print(f"✅ Mode set to: {mode}")
    else:
        print(f"❌ Error: {result}")


def cmd_resume(args):
    """Resume scheduled program."""
    thermostat_id = get_thermostat_id()
    
    body = {
        "selection": {
            "selectionType": "thermostats",
            "selectionMatch": thermostat_id
        },
        "functions": [{
            "type": "resumeProgram",
            "params": {
                "resumeAll": True
            }
        }]
    }
    
    params = {"format": "json"}
    result = api_request("/1/thermostat", method="POST", params=params, body=body)
    
    if result.get("status", {}).get("code") == 0:
        print("✅ Resumed scheduled program")
    else:
        print(f"❌ Error: {result}")


def cmd_sensors(args):
    """Show detailed sensor info."""
    thermostat_id = get_thermostat_id()
    
    selection = {
        "selection": {
            "selectionType": "thermostats",
            "selectionMatch": thermostat_id,
            "includeSensors": True
        }
    }
    
    params = {
        "format": "json",
        "json": json.dumps(selection),
        "_timestamp": int(time.time() * 1000)
    }
    
    result = api_request("/1/thermostat", params=params)
    
    thermostat = result.get("thermostatList", [{}])[0]
    sensors = thermostat.get("remoteSensors", [])
    
    print("\n📡 SENSORS")
    print("=" * 50)
    
    for sensor in sensors:
        name = sensor.get("name", "Unknown")
        sensor_type = sensor.get("type", "unknown")
        in_use = sensor.get("inUse", False)
        
        caps = {}
        for c in sensor.get("capability", []):
            caps[c["type"]] = c["value"]
        
        temp_f = float(caps.get("temperature", 0)) / 10.0 if "temperature" in caps else None
        humidity = caps.get("humidity")
        occupancy = caps.get("occupancy", "unknown")
        
        print(f"\n{name} ({sensor_type})")
        print(f"  In Use:    {'Yes' if in_use else 'No'}")
        if temp_f:
            temp_c = f_to_c(temp_f)
            print(f"  Temp:      {temp_c:.1f}°C ({temp_f:.1f}°F)")
        if humidity:
            print(f"  Humidity:  {humidity}%")
        print(f"  Occupied:  {'Yes' if occupancy == 'true' else 'No'}")


def cmd_hold(args):
    """Set a quick hold (home/away/sleep)."""
    thermostat_id = get_thermostat_id()
    
    climate = args.climate.lower()
    valid_climates = ["home", "away", "sleep"]
    
    if climate not in valid_climates:
        print(f"❌ Invalid climate. Choose from: {', '.join(valid_climates)}")
        sys.exit(1)
    
    hold_type = args.hold_type or "nextTransition"
    
    body = {
        "selection": {
            "selectionType": "thermostats",
            "selectionMatch": thermostat_id
        },
        "functions": [{
            "type": "setHold",
            "params": {
                "holdType": hold_type,
                "holdClimateRef": climate
            }
        }]
    }
    
    params = {"format": "json"}
    result = api_request("/1/thermostat", method="POST", params=params, body=body)
    
    if result.get("status", {}).get("code") == 0:
        print(f"✅ Set to '{climate}' hold")
        print(f"   Hold type: {hold_type}")
    else:
        print(f"❌ Error: {result}")


def cmd_raw(args):
    """Make a raw API call (for debugging)."""
    params = {
        "format": "json",
        "_timestamp": int(time.time() * 1000)
    }
    
    if args.json:
        params["json"] = args.json
    
    method = "POST" if args.post else "GET"
    body = json.loads(args.body) if args.body else None
    
    result = api_request(args.endpoint, method=method, params=params, body=body)
    print(json.dumps(result, indent=2))


def cmd_logout(args):
    """Clear saved credentials."""
    removed = []
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
        removed.append("token")
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()
        removed.append("session")
    
    if removed:
        print(f"✅ Cleared: {', '.join(removed)}")
    else:
        print("Nothing to clear")


def main():
    parser = argparse.ArgumentParser(
        description="Ecobee CLI - Control your Ecobee thermostat",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ecobee login              # One-time setup (opens browser)
  ecobee status             # Show current status
  ecobee set-temp 22        # Set to 22°C
  ecobee set-temp 72 -f     # Set to 72°F
  ecobee set-mode heat      # Set mode to heat
  ecobee hold home          # Set "Home" comfort setting
  ecobee resume             # Resume schedule
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Login
    subparsers.add_parser("login", help="Login to Ecobee (one-time setup)")
    
    # Logout
    subparsers.add_parser("logout", help="Clear saved credentials")
    
    # Status
    subparsers.add_parser("status", help="Show thermostat status")
    
    # Set temp
    temp_parser = subparsers.add_parser("set-temp", help="Set temperature hold")
    temp_parser.add_argument("temperature", type=float, help="Target temperature (Celsius by default)")
    temp_parser.add_argument("-f", "--fahrenheit", action="store_true", help="Temperature in Fahrenheit")
    temp_parser.add_argument("-t", "--hold-type", choices=["nextTransition", "indefinite", "holdHours"],
                            help="Hold type (default: nextTransition)")
    
    # Set mode
    mode_parser = subparsers.add_parser("set-mode", help="Set HVAC mode")
    mode_parser.add_argument("mode", choices=["heat", "cool", "auto", "off", "auxheatonly"])
    
    # Hold (comfort setting)
    hold_parser = subparsers.add_parser("hold", help="Set comfort setting hold")
    hold_parser.add_argument("climate", choices=["home", "away", "sleep"])
    hold_parser.add_argument("-t", "--hold-type", choices=["nextTransition", "indefinite", "holdHours"],
                            help="Hold type (default: nextTransition)")
    
    # Resume
    subparsers.add_parser("resume", help="Resume scheduled program")
    
    # Sensors
    subparsers.add_parser("sensors", help="Show sensor readings")
    
    # Raw (debug)
    raw_parser = subparsers.add_parser("raw", help="Make raw API call")
    raw_parser.add_argument("endpoint", help="API endpoint (e.g. /1/thermostat)")
    raw_parser.add_argument("-j", "--json", help="JSON query parameter")
    raw_parser.add_argument("-b", "--body", help="JSON body for POST")
    raw_parser.add_argument("-p", "--post", action="store_true", help="Use POST method")
    
    args = parser.parse_args()
    
    commands = {
        "login": cmd_login,
        "logout": cmd_logout,
        "status": cmd_status,
        "set-temp": cmd_set_temp,
        "set-mode": cmd_set_mode,
        "hold": cmd_hold,
        "resume": cmd_resume,
        "sensors": cmd_sensors,
        "raw": cmd_raw,
    }
    
    commands[args.command](args)


if __name__ == "__main__":
    main()
