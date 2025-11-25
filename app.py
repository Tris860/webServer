import json
import requests
import asyncio
from datetime import datetime
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

# --- Configuration ---
app = FastAPI()
SERVER_B_URL = os.environ.get("SERVER_B_URL", "https://iot-gateway-89zp.onrender.com/command")
PHP_BACKEND_URL = "https://tristechhub.org.rw/projects/ATS/backend/main.php?action=is_current_time_in_period"

connected_clients = set()

@app.get("/")
async def root():
    """Health check endpoint for Render and browsers."""
    return {"status": "ok", "message": "WebSocket server running"}

@app.websocket("/")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for browser clients."""
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

# --- New: PHP backend polling ---
async def check_php_backend():
    """Poll PHP backend and forward AUTO_ON when active period is found."""
    while True:
        try:
            resp = requests.get(PHP_BACKEND_URL, timeout=10)
            if resp.status_code != 200:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] PHP backend error: HTTP {resp.status_code}")
            else:
                raw = resp.text
                try:
                    data = json.loads(raw)
                except Exception:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Failed to parse backend response: {raw}")
                    data = None

                if data and data.get("success") is True:
                    message = f"TIME_MATCHED: {data.get('message')} : {data.get('id')}"
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Backend matched period → Forwarding AUTO_ON")

                    # Forward AUTO_ON to Server B
                    await forward_command("AUTO_ON")

                    # Notify connected browser clients
                    for ws in list(connected_clients):
                        try:
                            await ws.send_text(message)
                        except Exception:
                            pass
                else:
                    # Explicitly print the backend's failure message
                    backend_msg = data.get("message") if data else "No message"
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] PHP backend response indicates failure: {backend_msg}")
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] check_php_backend error: {e}")

        await asyncio.sleep(60)  # poll every 60 seconds

# --- Local run block ---
if __name__ == "__main__":
    import uvicorn

    loop = asyncio.get_event_loop()
    # Start background task
    loop.create_task(check_php_backend())

    port = int(os.environ.get("PORT", 5000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
