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

@app.on_event("startup")
async def start_php_polling():
    """Start the PHP backend polling task when FastAPI starts."""
    asyncio.create_task(check_php_backend())

@app.get("/")
async def root():
    return {"status": "ok", "message": "WebSocket server running"}

@app.websocket("/")
async def websocket_endpoint(websocket: WebSocket):
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

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Forwarding '{command}' to Server B...")
    try:
        response = requests.post(full_url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Server B replied: {response.text}")
            return f"✅ '{command}' forwarded. Server B replied: {response.text}"
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Server B error: HTTP {response.status_code}")
            return f"⚠️ Error: Server B responded with status {response.status_code}."
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Failed to connect to Server B: {e}")
        return f"❌ Failed to connect to Server B. {e.__class__.__name__}"

async def check_php_backend():
    """Poll PHP backend every minute and forward AUTO_ON when active period is matched."""
    while True:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Polling PHP backend...")
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

                if data:
                    backend_msg = data.get("message", "No message")
                    if data.get("success") is True:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ TIME MATCHED: {backend_msg} : {data.get('id')}")
                        await forward_command("AUTO_ON")
                        for ws in list(connected_clients):
                            try:
                                await ws.send_text(f"TIME_MATCHED: {backend_msg} : {data.get('id')}")
                            except Exception:
                                pass
                    else:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ TIME NOT MATCHED: {backend_msg}")
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] check_php_backend error: {e}")

        await asyncio.sleep(60)

# --- Local run block ---
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
