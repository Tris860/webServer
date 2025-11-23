# app.py
import json
import requests
from datetime import datetime
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

# --- Configuration ---
app = FastAPI()
SERVER_B_URL = os.environ.get("SERVER_B_URL", "https://iot-gateway-89zp.onrender.com/command")
connected_clients = set()

@app.get("/")
async def root():
    """Health check endpoint for Render and browsers."""
    return {"status": "ok", "message": "WebSocket server running"}

@app.websocket("/")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for clients (Wemos, browser UI)."""
    await websocket.accept()
    connected_clients.add(websocket)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Client connected. Total: {len(connected_clients)}")

    try:
        while True:
            command = await websocket.receive_text()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Received command: '{command}'")

            if not command:
                await websocket.send_text("⚠️ Error: Empty command received.")
                continue

            response = await forward_command(command)
            await websocket.send_text(response)

    except WebSocketDisconnect:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Client disconnected.")
    finally:
        connected_clients.remove(websocket)

async def forward_command(command: str):
    """Forward command to Server B via HTTP POST."""
    full_url = SERVER_B_URL if SERVER_B_URL.endswith('/command') else f"{SERVER_B_URL}/command"
    payload = {"command": command, "source": "ServerA"}

    try:
        response = requests.post(full_url, json=payload, timeout=10)
        if response.status_code == 200:
            return f"✅ '{command}' forwarded. Server B replied: {response.text}"
        else:
            return f"⚠️ Error: Server B responded with status {response.status_code}."
    except requests.exceptions.RequestException as e:
        return f"❌ Failed to connect to Server B. {e.__class__.__name__}"

# --- Local run block (optional for dev) ---
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
