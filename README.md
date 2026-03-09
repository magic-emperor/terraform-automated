# Automated Terraform Manager

A full-stack application for managing and auto-destroying local Terraform deployments. 

## Features
- Execute `terraform init`, `plan`, and `apply` asynchronously.
- Live WebSockets streaming of Terraform Execution logs to a modern Vue.js dashboard.
- Configurable countdown timer that automatically executes `terraform destroy` when it expires.
- Manual early destroy override.

## Usage
Refer to the `walkthrough.md` documentation for instructions on running the FastAPI backend and Vue frontend locally.
