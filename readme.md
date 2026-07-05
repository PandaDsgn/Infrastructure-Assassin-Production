# Infrastructure Assassin

[![Deployment Status](https://img.shields.io/badge/Deployment-Render-success?style=flat-square&logo=render)](#)
[![Security AI](https://img.shields.io/badge/AI_Engine-Multi--Tier_Waterfall-blue?style=flat-square)](#)
[![Version](https://img.shields.io/badge/Version-Production-brightgreen?style=flat-square)](#)

## Project Overview

**Infrastructure Assassin** is an automated, enterprise-grade IT security and cloud management platform. Designed to aggressively monitor cloud environments, the system identifies infrastructural waste, uncovers malicious threats, and executes automated remediation protocols. 

The core of Infrastructure Assassin is its highly resilient, multi-tier AI waterfall architecture, which seamlessly balances advanced cloud LLMs with a local heuristics engine to guarantee continuous security monitoring and high uptime. Through a centralized dashboard, teams can efficiently track resource utilization, terminate idle assets, and quarantine active threats in real-time.

---

## Key Features

### Automated Security & Threat Detection
*   **Active Monitoring:** Continuously scans cloud architectures for vulnerabilities, configuration drifts, and anomalous behaviors.
*   **Threat Quarantining:** Automatically isolates and quarantines malicious instances or compromised resources before they can spread laterally across the network.
*   **Local Heuristics Engine:** A fail-safe local engine that ensures baseline security and threat detection remain operational even if external API connections are interrupted.

### Cloud Waste Assassination
*   **Resource Tracking:** Identifies orphaned, over-provisioned, or completely idle cloud assets.
*   **Automated Termination:** Safely spins down and terminates unnecessary resources to drastically reduce cloud expenditure.

### Multi-Tier AI Waterfall System
*   **Dynamic Load Balancing:** Intelligently routes queries and analysis tasks across leading LLM providers to ensure the highest quality insights and avoid rate-limiting.
*   **Supported Models:** Fully integrated with **Gemini**, **Claude**, **OpenAI**, and **Grok**.
*   **Failover Resilience:** Automatically cascades down the AI tier list if a primary LLM service experiences downtime, ultimately falling back to the local heuristics engine.

### Role-Based Access Control (RBAC)
*   **Directors:** Full administrative oversight. Can approve broad termination policies, manage AI tier routing, and review high-level security audits.
*   **Developers:** Granular access for viewing asset logs, manually quarantining isolated threats, and testing infrastructure deployments.

---

## Architecture & Deployment

The system is compartmentalized into two primary services to ensure separation of concerns:

1.  **`Infrastructure-Assassin-Production`**: The core backend engine handling the AI waterfall, cloud API integrations, and the local heuristics ruleset.
2.  **`Infrastructure-Assassin-Dash`**: The frontend web interface providing the real-time visual telemetry, RBAC enforcement, and manual override controls.

Both services are optimized for cloud deployment and are actively configured for hosting via **Render**.

---

## Installation & Setup

### Prerequisites
*   Node.js (v18+)
*   Python 3.10+ (for the heuristics engine)
*   Active API keys for required AI providers (Google Gemini, Anthropic Claude, OpenAI, xAI Grok)
*   Target Cloud Provider CLI/Credentials (AWS, GCP, or Azure) configured locally.

### Environment Configuration
Clone the repository and configure the environment variables for both the dashboard and production services.

```bash
git clone [https://github.com/your-org/Infrastructure-Assassin.git](https://github.com/your-org/Infrastructure-Assassin.git)
cd Infrastructure-Assassin

# Configure Production Backend
cd Infrastructure-Assassin-Production
cp .env.example .env
# Add your AI API keys and Cloud IAM credentials to .env
npm install
npm run start:prod

# Configure Dashboard Frontend
cd ../Infrastructure-Assassin-Dash
cp .env.example .env
npm install
npm run build
npm run start
