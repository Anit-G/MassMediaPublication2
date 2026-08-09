#!/usr/bin/env python3
"""
Script to manually or automatically trigger token refresh for YouTube channels.

Channels are processed in the strict sequence:
1. Echo's Slumber (UCXeqq2XcvF7jjEcv35dPl8A, cat(RS))
2. Erebus Echoes (UCfOw-0ovjVZSE8HvaCNJJ_Q, cat(MS))
3. MoonBerry Echoes (UCKpi4fdhxKbO_DWUD3FODTA, cat(WE))
4. Marrow and Manuscripts (UChDu5fX4ICAQSgdT653TGzA, cat(LM))
"""

import sys
import os
import json
import argparse
from typing import Dict, Any, List, Optional

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import Utils.Central_Logger as log
import Utils.Config_vars as config
from Utils.DB_Operations import DBOps

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    HAS_GOOGLE_AUTH = True
except ImportError:
    InstalledAppFlow = None
    Credentials = None
    Request = None
    HAS_GOOGLE_AUTH = False

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube"
]

TARGET_CHANNELS = [
    {
        "name": "Echo's Slumber",
        "channel_id": "UCXeqq2XcvF7jjEcv35dPl8A",
        "category": "cat(RS)",
        "handle": "@EchoSlumber"
    },
    {
        "name": "Erebus Echoes",
        "channel_id": "UCfOw-0ovjVZSE8HvaCNJJ_Q",
        "category": "cat(MS)",
        "handle": "@ErebosEchoes"
    },
    {
        "name": "MoonBerry Echoes",
        "channel_id": "UCKpi4fdhxKbO_DWUD3FODTA",
        "category": "cat(WE)",
        "handle": "@MoonBerryEchoes"
    },
    {
        "name": "Marrow and Manuscripts",
        "channel_id": "UChDu5fX4ICAQSgdT653TGzA",
        "category": "cat(LM)",
        "handle": "@MarrowManuscripts"
    }
]


def load_client_secret(dbops: DBOps) -> Optional[Dict[str, Any]]:
    """Attempt to load client secrets from DB KVS or local filesystem."""
    try:
        secret = dbops.get_client_secret()
        if secret:
            return secret
    except Exception as e:
        log.WARNING(f"Could not load client_secret from DB: {e}")

    secret_path = "./Data/Secrets/client_secrets.json"
    if os.path.exists(secret_path):
        try:
            with open(secret_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.ERROR(f"Error loading client_secrets.json: {e}")

    return None


def inspect_channel_token(dbops: DBOps, channel_id: str) -> Dict[str, Any]:
    """Inspect current token state in DB for a channel."""
    token = dbops.get_channel_token(channel_id)
    if not token:
        return {"status": "missing", "valid": False, "expired": True, "has_refresh_token": False}

    if not HAS_GOOGLE_AUTH:
        return {"status": "stored_no_sdk", "valid": True, "expired": False, "has_refresh_token": True}

    try:
        creds = Credentials.from_authorized_user_info(token, SCOPES)
        return {
            "status": "valid" if creds.valid else ("expired" if creds.expired else "invalid"),
            "valid": creds.valid,
            "expired": creds.expired,
            "has_refresh_token": bool(creds.refresh_token),
            "expiry": creds.expiry.isoformat() if creds.expiry else None
        }
    except Exception as e:
        return {"status": "corrupt", "valid": False, "expired": True, "has_refresh_token": False, "error": str(e)}


def refresh_single_channel(
    dbops: DBOps,
    channel: Dict[str, str],
    force_manual: bool = False,
    interactive: bool = False
) -> Dict[str, Any]:
    """
    Refresh or authenticate token for a single channel.
    Returns status report dictionary.
    """
    channel_name = channel["name"]
    channel_id = channel["channel_id"]
    category = channel["category"]

    log.INFO(f"Processing YouTube Token Refresh for [{channel_name}] ({channel_id})...")

    result = {
        "channel_name": channel_name,
        "channel_id": channel_id,
        "category": category,
        "action_taken": "none",
        "success": False,
        "message": ""
    }

    if not HAS_GOOGLE_AUTH:
        result["message"] = "Google API packages (google-auth-oauthlib / googleapiclient) not installed"
        log.WARNING(f"[{channel_name}]: {result['message']}")
        return result

    token_info = inspect_channel_token(dbops, channel_id)

    # 1. Automatic refresh attempt if token exists, expired, and has refresh_token (unless force_manual is requested)
    if token_info.get("has_refresh_token") and not force_manual:
        try:
            raw_token = dbops.get_channel_token(channel_id)
            creds = Credentials.from_authorized_user_info(raw_token, SCOPES)

            if creds.valid:
                result["action_taken"] = "none_valid"
                result["success"] = True
                result["message"] = "Token is already valid"
                log.INFO(f"[{channel_name}]: Token is valid. No action needed.")
                return result

            # Attempt refresh
            log.INFO(f"[{channel_name}]: Attempting automatic token refresh using refresh_token...")
            creds.refresh(Request())

            if creds.valid:
                creds_json = creds.to_json()
                dbops.set_channel_token(channel_id, creds_json)

                # Backup to Data/Secrets/
                os.makedirs("./Data/Secrets", exist_ok=True)
                with open(f"./Data/Secrets/token_{channel_id}.json", "w", encoding="utf-8") as f:
                    f.write(creds_json)

                result["action_taken"] = "auto_refreshed"
                result["success"] = True
                result["message"] = "Token refreshed automatically and updated in DB"
                log.INFO(f"[{channel_name}]: Token successfully refreshed automatically!")
                return result

        except Exception as e:
            log.WARNING(f"[{channel_name}]: Automatic token refresh failed: {e}. Moving to manual/interactive flow.")

    # 2. Interactive Browser Re-authentication Flow
    client_secret_data = load_client_secret(dbops)
    if not client_secret_data:
        result["action_taken"] = "needs_manual_auth"
        result["success"] = False
        result["message"] = "Client secrets missing from DB and Data/Secrets/client_secrets.json"
        log.ERROR(f"[{channel_name}]: Cannot start OAuth flow: client secret missing")
        return result

    try:
        log.INFO(f"[{channel_name}]: Initializing InstalledAppFlow for browser re-authentication...")
        flow = InstalledAppFlow.from_client_config(client_secret_data, SCOPES)

        if interactive:
            print(f"\n=======================================================")
            print(f" AUTHENTICATION PROMPT FOR: {channel_name} ({channel['handle']})")
            print(f" Please authenticate this channel in your browser window.")
            print(f"=======================================================\n")
            creds = flow.run_local_server(port=0, prompt="consent")

            creds_json = creds.to_json()
            dbops.set_channel_token(channel_id, creds_json)

            os.makedirs("./Data/Secrets", exist_ok=True)
            with open(f"./Data/Secrets/token_{channel_id}.json", "w", encoding="utf-8") as f:
                f.write(creds_json)

            result["action_taken"] = "interactive_authenticated"
            result["success"] = True
            result["message"] = "Successfully authenticated interactively and stored token in DB"
            log.INFO(f"[{channel_name}]: Interactive OAuth completion successful!")
        else:
            # Generate auth URL for non-blocking browser navigation
            auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
            result["action_taken"] = "auth_url_generated"
            result["auth_url"] = auth_url
            result["success"] = False
            result["message"] = "Manual browser authentication required. Navigate to auth_url to complete."
            log.INFO(f"[{channel_name}]: Auth URL generated for browser authentication.")

    except Exception as e:
        result["action_taken"] = "failed"
        result["success"] = False
        result["message"] = f"OAuth flow error: {e}"
        log.ERROR(f"[{channel_name}]: OAuth flow error: {e}")

    return result


def run_sequence(
    force_manual: bool = False,
    interactive: bool = False,
    filter_channel: Optional[str] = None
) -> Dict[str, Any]:
    """Run token refresh across all 4 channels in exact sequence."""
    dbops = DBOps()
    reports = []

    channels = TARGET_CHANNELS
    if filter_channel:
        channels = [c for c in TARGET_CHANNELS if filter_channel.lower() in c["name"].lower() or filter_channel.lower() in c["channel_id"].lower()]

    log.INFO("=========================================================================")
    log.INFO("Starting YouTube Channel Token Refresh Sequence")
    log.INFO("Sequence: Echo's Slumber -> Erebus Echoes -> MoonBerry Echoes -> Marrow and Manuscripts")
    log.INFO("=========================================================================")

    all_success = True
    for ch in channels:
        rep = refresh_single_channel(dbops, ch, force_manual=force_manual, interactive=interactive)
        reports.append(rep)
        if not rep["success"]:
            all_success = False

    return {
        "sequence_order": [c["name"] for c in TARGET_CHANNELS],
        "all_success": all_success,
        "channel_reports": reports
    }


def main():
    parser = argparse.ArgumentParser(description="Refresh YouTube API tokens for channels in sequence.")
    parser.add_argument("--force", action="store_true", help="Force manual interactive OAuth re-authentication")
    parser.add_argument("--interactive", action="store_true", help="Run local server for browser popup prompt")
    parser.add_argument("--channel", type=str, help="Specific channel name filter")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    results = run_sequence(force_manual=args.force, interactive=args.interactive, filter_channel=args.channel)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("\n--- TOKEN REFRESH SUMMARY ---")
        for r in results["channel_reports"]:
            status = "✅ OK" if r["success"] else "⚠️ ATTENTION"
            print(f"{status} | {r['channel_name']} ({r['channel_id']}): {r['message']} [Action: {r['action_taken']}]")
            if "auth_url" in r and r["auth_url"]:
                print(f"  --> Auth URL: {r['auth_url']}")


if __name__ == "__main__":
    main()
