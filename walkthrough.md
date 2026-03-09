# Automated Terraform Manager - Walkthrough & Handover

This document outlines how to run and use the Automated Terraform Manager locally.

## Prerequisites

Before running this application, the host system **MUST** have Terraform installed and available in the system `PATH`. The application relies on executing `terraform` commands directly via the shell.

- Download Terraform here: [https://developer.hashicorp.com/terraform/downloads](https://developer.hashicorp.com/terraform/downloads)
- Verify installation by opening a terminal and running `terraform -version`.

## Running the Application Locally

The application consists of a Python FastAPI backend and a Vue.js frontend. They must both be running simultaneously.

### 1. Start the Backend

Open a new terminal and navigate to the `backend` directory:
```bash
cd d:/Shafi/backend
```

Install the dependencies (if not already done):
```bash
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

Run the FastAPI server:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
*The backend will be available at `http://localhost:8000`.*

### 2. Start the Frontend

Open a second terminal and navigate to the `frontend` directory:
```bash
cd d:/Shafi/frontend
```

Install Node.js dependencies (if not already done):
```bash
npm install
```

Start the Vite development server:
```bash
npm run dev
```
*The frontend will be available at `http://localhost:5173` (or the port specified in the terminal output).*

## How to Use

1. **Open the Application:** Navigate to `http://localhost:5173` in your web browser.
2. **Setup Deployment:**
    - Provide the **absolute path** to a directory containing your `.tf` configuration files (e.g., `C:/Projects/my-terraform-project`).
    - Specify the **Auto-Destroy** timeframe in hours. (You can use decimals like `0.5` for 30 minutes, or `0.01` for testing).
3. **Deploy:** Click **Initialize & Deploy**.
    - The backend will sequentially execute `terraform init`, `terraform plan`, and `terraform apply -auto-approve`.
    - Live logs from these commands will stream directly to the UI via WebSockets.
4. **Active State:** Once deployed, the application enters the 'Active' state and the countdown timer begins.
5. **Destruction:**
    - **Automatic:** When the timer hits `00:00:00`, the backend will automatically execute `terraform destroy -auto-approve`.
    - **Manual:** At any point while the timer is running, you can click the red **Destroy Now** button to immediately trigger the destruction process.

## Architecture Highlights

- **FastAPI Background Tasks:** The scheduling is handled entirely in-memory using `asyncio` background tasks. There is no need for Celery or Redis for local usage.
- **WebSocket Streaming:** `main.py` creates asynchronous shell subprocesses and streams the `stdout` and `stderr` directly to connected WebSocket clients to give the user real-time feedback.
- **Auto-Approve:** The system bypasses human prompts using the `-auto-approve` flag during `apply` and `destroy` operations.

## GitHub Push Instructions

If anyone is planning to contribute or push new code to this repository, you **must** follow the standard Pull Request (PR) workflow:

1. **Do not push directly to `main`.**
2. **Create a new branch** for your feature or bug fix:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Commit your changes** with descriptive messages:
   ```bash
   git add .
   git commit -m "Add descriptive message here"
   ```
4. **Push the branch** to GitHub:
   ```bash
   git push -u origin feature/your-feature-name
   ```
5. **Raise a Pull Request (PR)** on GitHub targeting the `main` branch, and wait for review/approval before merging.
