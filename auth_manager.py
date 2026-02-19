#!/usr/bin/env python3
"""
Authentication Manager for Podcast Agent
Handles Google login and browser state persistence
"""

import json
import time
import argparse
import shutil
import re
import sys
from pathlib import Path
from typing import Optional, Dict, Any

from patchright.sync_api import sync_playwright, BrowserContext

# Add parent directory to path to allow importing lib
sys.path.insert(0, str(Path(__file__).parent))

from lib.config import BROWSER_STATE_DIR, STATE_FILE, AUTH_INFO_FILE, DATA_DIR
from lib.browser_utils import BrowserFactory


class AuthManager:
    """
    Manages authentication and browser state for NotebookLM
    """

    def __init__(self):
        """Initialize the authentication manager"""
        # Ensure directories exist
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        BROWSER_STATE_DIR.mkdir(parents=True, exist_ok=True)

        self.state_file = STATE_FILE
        self.auth_info_file = AUTH_INFO_FILE
        self.browser_state_dir = BROWSER_STATE_DIR

    def is_authenticated(self) -> bool:
        """Check if valid authentication exists"""
        if not self.state_file.exists():
            return False

        # Check if state file is not too old (7 days)
        age_days = (time.time() - self.state_file.stat().st_mtime) / 86400
        if age_days > 7:
            print(f"Browser state is {age_days:.1f} days old, may need re-authentication")

        return True

    def get_auth_info(self) -> Dict[str, Any]:
        """Get authentication information"""
        info = {
            'authenticated': self.is_authenticated(),
            'state_file': str(self.state_file),
            'state_exists': self.state_file.exists()
        }

        if self.auth_info_file.exists():
            try:
                with open(self.auth_info_file, 'r') as f:
                    saved_info = json.load(f)
                    info.update(saved_info)
            except Exception:
                pass

        if info['state_exists']:
            age_hours = (time.time() - self.state_file.stat().st_mtime) / 3600
            info['state_age_hours'] = age_hours

        return info

    def setup_auth(self, headless: bool = False, timeout_minutes: int = 10) -> bool:
        """
        Perform interactive authentication setup
        """
        print("Starting authentication setup...")
        print(f"  Timeout: {timeout_minutes} minutes")

        playwright = None
        context = None

        try:
            playwright = sync_playwright().start()

            # Launch using factory
            context = BrowserFactory.launch_persistent_context(
                playwright,
                headless=headless
            )

            # Navigate to NotebookLM
            page = context.new_page()
            page.goto("https://notebooklm.google.com", wait_until="domcontentloaded")

            # Check if already authenticated
            if "notebooklm.google.com" in page.url and "accounts.google.com" not in page.url:
                print("  Already authenticated!")
                self._save_browser_state(context)
                return True

            # Wait for manual login
            print("\n  Please log in to your Google account...")
            print(f"  Waiting up to {timeout_minutes} minutes for login...")

            try:
                # Wait for URL to change to NotebookLM
                timeout_ms = int(timeout_minutes * 60 * 1000)
                page.wait_for_url(re.compile(r"^https://notebooklm\.google\.com/"), timeout=timeout_ms)

                print(f"  Login successful!")

                # Save authentication state
                self._save_browser_state(context)
                self._save_auth_info()
                return True

            except Exception as e:
                print(f"  Authentication timeout: {e}")
                return False

        except Exception as e:
            print(f"  Error: {e}")
            return False

        finally:
            # Clean up browser resources
            if context:
                try:
                    context.close()
                except Exception:
                    pass

            if playwright:
                try:
                    playwright.stop()
                except Exception:
                    pass

    def _save_browser_state(self, context: BrowserContext):
        """Save browser state to disk"""
        try:
            # Save storage state (cookies, localStorage)
            context.storage_state(path=str(self.state_file))
            print(f"  Saved browser state to: {self.state_file}")
        except Exception as e:
            print(f"  Failed to save browser state: {e}")
            raise

    def _save_auth_info(self):
        """Save authentication metadata"""
        try:
            info = {
                'authenticated_at': time.time(),
                'authenticated_at_iso': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            with open(self.auth_info_file, 'w') as f:
                json.dump(info, f, indent=2)
        except Exception:
            pass  # Non-critical

def main():
    parser = argparse.ArgumentParser(description='Manage NotebookLM authentication')
    parser.add_argument('command', choices=['setup', 'status'], help='Command to run')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    args = parser.parse_args()

    auth = AuthManager()

    if args.command == 'setup':
        if auth.setup_auth(headless=args.headless):
            print("\nAuthentication setup complete!")
        else:
            print("\nAuthentication setup failed")
            exit(1)
    elif args.command == 'status':
        print(auth.get_auth_info())

if __name__ == "__main__":
    main()
