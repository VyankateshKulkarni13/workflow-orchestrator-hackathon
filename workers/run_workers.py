"""
run_workers.py
--------------
Single-command launcher for all 5 mock workers.

Imports all worker modules (which auto-register their handlers via @register),
then starts the unified base_worker listener loop.

Usage:
    cd workers
    python run_workers.py

This replaces the need to open 5 separate terminals.
"""
import sys
import os

# Ensure 'workers/' is on sys.path so base_worker is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import all worker modules — each one registers its handler via @register(...)
import order_validation_worker   # noqa: F401 (registers "validate_order")
import payment_worker            # noqa: F401 (registers "charge_payment")
import inventory_worker          # noqa: F401 (registers "update_inventory")
import shipping_worker           # noqa: F401 (registers "prepare_shipping")
import notification_worker       # noqa: F401 (registers "send_confirmation")

# Now start the single shared Redis listener with all handlers registered
from base_worker import run

if __name__ == "__main__":
    run()
