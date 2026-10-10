"""Background service entry point: 15-minute weather refresh (see lib/addon.run_refresh_service)."""
from lib import addon

if __name__ == '__main__':
    addon.run_refresh_service()
