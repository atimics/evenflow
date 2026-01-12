#!/usr/bin/env python3
"""
Configure Evennia for Codespace/external access and create AWS deployment.
"""
import os

SETTINGS_PATH = "/workspaces/evenflow_game/server/conf/settings.py"

# Read current settings
with open(SETTINGS_PATH, 'r') as f:
    content = f.read()

# Settings to append for external access
external_settings = '''
# =============================================================
# Codespace/External Access Settings
# =============================================================

# Allow connections from forwarded ports
ALLOWED_HOSTS = ["*"]

# Bind to all interfaces
WEBSERVER_INTERFACES = [("0.0.0.0", 4001)]
WEBSOCKET_CLIENT_INTERFACE = "0.0.0.0"
TELNET_INTERFACES = [("0.0.0.0", 4000)]

# CSRF and security settings for external access
CSRF_TRUSTED_ORIGINS = [
    "https://*.github.dev",
    "https://*.preview.app.github.dev", 
    "https://*.app.github.dev",
    "http://localhost:4001",
    "http://127.0.0.1:4001",
]

# Enable debug for development
DEBUG = True

# Webclient settings
WEBCLIENT_ENABLED = True
'''

# Check if already configured
if "Codespace/External Access Settings" not in content:
    with open(SETTINGS_PATH, 'a') as f:
        f.write(external_settings)
    print("✓ Added external access settings to Evennia config")
else:
    print("✓ External access settings already configured")

print(f"Settings file: {SETTINGS_PATH}")
