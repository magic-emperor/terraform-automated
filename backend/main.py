import asyncio
from fastapi import FastAPI, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import json
import uuid
import datetime
import shutil

app = FastAPI(title="Terraform Manager API")

# Setup CORS to allow the Vue frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory state tracking for simplicity
# Format: {"deployment_id": {"status": "Active", "destroy_at": "timestamp", "log": [...]}}
deployments = {}

# Active websocket connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

class DeployRequest(BaseModel):
    tf_dir: str
    destroy_time_hours: float

async def stream_subprocess(cmd: str, cwd: str, session_id: str, stage: str):
    """Run a subprocess and stream its output to websockets."""
    await manager.broadcast({"type": "stage_update", "session_id": session_id, "stage": stage})
    
    try:
        process = await asyncio.create_subprocess_shell(
            cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception as e:
        await manager.broadcast({"type": "log", "session_id": session_id, "stage": stage, "stream": "stderr", "text": f"Failed to start process: {e}"})
        return -1
    
    async def read_stream(stream, stream_type):
        while True:
            line = await stream.readline()
            if not line:
                break
            text = line.decode('utf-8').rstrip()
            await manager.broadcast({"type": "log", "session_id": session_id, "stage": stage, "stream": stream_type, "text": text})

    await asyncio.gather(
        read_stream(process.stdout, "stdout"),
        read_stream(process.stderr, "stderr")
    )
    await process.wait()
    return process.returncode

async def execute_terraform_deploy(session_id: str, tf_dir: str, destroy_in_seconds: int):
    # Update state
    deployments[session_id] = {"status": "Deploying", "tf_dir": tf_dir}
    
    # Fallback to absolute path if not in system PATH
    tf_cmd = "terraform"
    if not shutil.which("terraform"):
        tf_cmd = "D:/Downloads/terraform_1.14.6_amd64/terraform.exe"

    try:
        # 1. Initialize
        code = await stream_subprocess(f"{tf_cmd} init", tf_dir, session_id, "Initializing")
        if code != 0:
            raise Exception("Terraform init failed")

        # 2. Plan
        code = await stream_subprocess(f"{tf_cmd} plan -out=tfplan", tf_dir, session_id, "Planning")
        if code != 0:
            raise Exception("Terraform plan failed")

        # 3. Apply
        code = await stream_subprocess(f"{tf_cmd} apply -auto-approve tfplan", tf_dir, session_id, "Applying")
        if code != 0:
            raise Exception("Terraform apply failed")

        # Success - Active
        destroy_at = datetime.datetime.now() + datetime.timedelta(seconds=destroy_in_seconds)
        deployments[session_id]["status"] = "Active"
        deployments[session_id]["destroy_at"] = destroy_at.isoformat()
        
        await manager.broadcast({"type": "status_update", "session_id": session_id, "status": "Active", "destroy_at": destroy_at.isoformat()})

        # Wait for the destroy time
        while datetime.datetime.now() < destroy_at and deployments.get(session_id, {}).get("status") == "Active":
            await asyncio.sleep(1)

        # If it wasn't manually destroyed earlier, run destroy
        if deployments.get(session_id, {}).get("status") == "Active":
            await execute_terraform_destroy(session_id, tf_dir)

    except Exception as e:
        print(f"Deployment failed: {e}")
        deployments[session_id]["status"] = "Failed"
        deployments[session_id]["error"] = str(e)
        await manager.broadcast({"type": "status_update", "session_id": session_id, "status": "Failed", "error": str(e)})

async def execute_terraform_destroy(session_id: str, tf_dir: str):
    # Check if actually deployed
    deployments[session_id]["status"] = "Destroying"
    
    tf_cmd = "terraform"
    if not shutil.which("terraform"):
        tf_cmd = "D:/Downloads/terraform_1.14.6_amd64/terraform.exe"
    
    try:
        code = await stream_subprocess(f"{tf_cmd} destroy -auto-approve", tf_dir, session_id, "Destroying")
        if code != 0:
            raise Exception("Terraform destroy failed")
            
        deployments[session_id]["status"] = "Destroyed"
        await manager.broadcast({"type": "status_update", "session_id": session_id, "status": "Destroyed"})
    except Exception as e:
        deployments[session_id]["status"] = "Destroy Failed"
        await manager.broadcast({"type": "status_update", "session_id": session_id, "status": "Destroy Failed", "error": str(e)})

@app.post("/api/terraform/deploy")
async def deploy_terraform(req: DeployRequest, background_tasks: BackgroundTasks):
    if not os.path.exists(req.tf_dir):
        return {"error": f"Directory not found: {req.tf_dir}"}
        
    session_id = str(uuid.uuid4())
    destroy_seconds = int(req.destroy_time_hours * 3600)
    
    background_tasks.add_task(execute_terraform_deploy, session_id, req.tf_dir, destroy_seconds)
    
    return {"session_id": session_id, "message": "Deployment scheduled"}

@app.post("/api/terraform/destroy/{session_id}")
async def force_destroy(session_id: str, background_tasks: BackgroundTasks):
    if session_id not in deployments:
        return {"error": "Session not found"}
        
    session_data = deployments[session_id]
    
    if session_data["status"] != "Active":
         return {"error": f"Cannot destroy in current state: {session_data['status']}"}
         
    # Update status so the original destroy loop cancels
    session_data["status"] = "Manual Destroy Triggered"
    
    background_tasks.add_task(execute_terraform_destroy, session_id, session_data["tf_dir"])
    
    return {"message": "Manual destroy initiated"}

@app.get("/api/terraform/status/{session_id}")
async def get_status(session_id: str):
    if session_id not in deployments:
        return {"error": "Session not found"}
    return deployments[session_id]

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # We don't really expect clients to send much, maybe ping/pong
    except WebSocketDisconnect:
        manager.disconnect(websocket)
