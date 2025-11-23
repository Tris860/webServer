# app.py
import asyncio
import websockets
import json
import requests
from datetime import datetime
import os

# --- Configuration ---
WS_HOST = "0.0.0.0"
WS_PORT = int(os.environ.get("PORT", 8765))  # Render sets this automatically
SERVER_B_URL = os.environ.get("SERVER_B_URL", "https://iot-gateway-89zp.onrender.com/command")

CONNECTED_CLIENTS = set()

async def forward_command(command: str):
    """Forward command to Server B via HTTP POST."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Forwarding '{command}' to Server B at {SERVER_B_URL}...")
    full_url = SERVER_B_URL if SERVER_B_URL.endswith('/command') else f"{SERVER_B_URL}/command"

    try:
        payload = {"command": command, "source": "ServerA"}
        response = requests.post(full_url, json=payload, timeout=10)

        if response.status_code == 200:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Server B acknowledged command. Response: {response.text}")
            return f"✅ '{command}' forwarded successfully. Server B replied: {response.text}"
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Server B returned error status: {response.status_code}")
            return f"⚠️ Error: Server B responded with status {response.status_code}."

    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: Failed to reach Server B. Details: {e}")
        return f"❌ Failed to connect to Server B. {e.__class__.__name__}"

async def handler(websocket, path):
    """Handle incoming WebSocket connections and messages."""
    CONNECTED_CLIENTS.add(websocket)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Client connected. Total: {len(CONNECTED_CLIENTS)}")

    try:
        async for message in websocket:
            command = message.strip()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Received command: '{command}'")

            if not command:
                await websocket.send("⚠️ Error: Empty command received.")
                continue

            response = await forward_command(command)
            await websocket.send(response)

    except websockets.exceptions.ConnectionClosedOK:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Client disconnected gracefully.")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Unexpected error: {e}")
    finally:
        CONNECTED_CLIENTS.remove(websocket)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Client disconnected. Total: {len(CONNECTED_CLIENTS)}")

async def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting Server A on ws://{WS_HOST}:{WS_PORT}")
    async with websockets.serve(handler, WS_HOST, WS_PORT):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer A stopped by user.")
    except Exception as e:
        print(f"Startup error: {e}")
