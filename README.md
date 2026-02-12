# TrustPoll-AI
A decentralized, AI-fortified voting protocol for transparent campus governance.

## Problem Statement
Campus elections and governance systems often suffer from a lack of transparency, leading to mistrust among the student body. Traditional electronic voting systems are centralized, making them vulnerable to database tampering, administrative manipulation, and opaque vote counting processes. Verifying the integrity of an election without technical expertise is nearly impossible for the average student.

## Our Solution
TrustPoll-AI bridges the gap between Web2 usability and Web3 security. We provide a **hybrid decentralization model** that allows students to vote using familiar credentials (university email) while leveraging the **Algorand blockchain** to immutably record votes and enforce election rules. An AI-powered Fairness Index monitors the system in real-time to detect anomalies and insider threats.

## System Architecture
![Architecture Diagram](Architectre_Diagram.png)

## Decentralization Model

| Component | Implementation | Type | Purpose |
| :--- | :--- | :--- | :--- |
| **Authentication** | Email + OTP (Vit.edu) | Centralized | Ensures only valid students vote without managing wallets. |
| **Vote Storage** | PostgreSQL + Algorand | Hybrid | DB for speed; Blockchain for immutable truth. |
| **Vote Counting** | Algorand Smart Contract | Decentralized | Enforces logic, deadlines, and final tally. |
| **Audit Logs** | Algorand Anchoring | Decentralized | Prevents admin tampering of critical logs. |
| **Integrity** | AI Fairness Index | Hybrid | Analyzes patterns to detect fraud/coercion. |

## Blockchain Integration
TrustPoll-AI utilizes the **Algorand Blockchain** as the source of truth.
- **Vote Enforcement**: A custom Smart Contract governs the election state. It enforces start and end timestamps, ensuring no votes can be cast outside the voting window.
- **Immutable Tally**: Votes are submitted as transactions to the smart contract. The contract maintains the global state of candidate counts, making the results mathematically verifiable and impossible to alter via database manipulation.
- **Tamper-Proof Audit**: Critical administrative actions and the "Fairness Index" snapshots are hashed and anchored on-chain.

## Novel Features
- **Gasless Voting**: Students do not need ALGO or a wallet. A backend service wallet handles blockchain interactions transparently.
- **Hybrid Decentralization**: Combines the speed of PostgreSQL with the trust of Algorand, ensuring a seamless user experience without compromising security.
- **AI Fairness Index**: Computes an election integrity score (0-100%) based on tampering attempts, duplicate blocks, and timing anomalies.
- **Insider Threat Detection**: Compares anchored admin hashes against database records to flag `CRITICAL_ADMIN_LOG_TAMPERING`.
- **Governance Audit**: Automatically lowers the Fairness Index if governance compromises are detected.

## Smart Contract Details
- **Network**: Algorand TestNet
- **Enforcement Logic**:
  - **Registration**: Whitelisted via backend auth.
  - **Voting Window**: Strict timestamp enforcement on-chain.
  - **Tallying**: Real-time on-chain counter increment.
- **App ID**: *(Configured in Environment as `ALGORAND_APP_ID`)*

## Project Structure
- **`backend/`**: Contains the Flask API, Smart Contract interaction logic, and the AI Fairness Index computation engine.
- **`trustpoll-frontend/`**: The Next.js web application providing the voter interface and admin dashboard.
- **`README.md`**: Includes architecture diagrams and supplementary documentation.

## Setup Instructions

### 1. Backend Environment
Navigate to `backend/` and create a `.env` file based on `.env.testnet.example`.

### 2. Deploy Smart Contract
To generate a fresh election instance on the blockchain:
```powershell
cd backend
.\.venv\Scripts\Activate.ps1  # or source .venv/bin/activate on Linux/Mac
pip install -r requirements.txt
python deploy_contract.py
```
**Action Required**: Copy the output **App ID** and paste it into your `backend/.env` file as `ALGORAND_APP_ID`.

### 3. Start Backend
With the App ID configured, start the server:
```powershell
# Ensure you are in backend/ with venv active
python app.py
```

Backend runs on `http://localhost:5000`.

### 4. Start Frontend
```powershell
cd trustpoll-frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:3000`.

### 5. Funding Estimate
Each anchor is a 0-ALGO self-payment with network fee (`~0.001 ALGO/tx`).
With `10 ALGO`, you can typically support around `9,800-9,900` anchored vote events.

## Environment Variables
Ensure the following are set in your `backend/.env`:

- **Database**: `DATABASE_URL` (PostgreSQL connection string)
- **Email Service**: `SMTP_HOST`, `SMTP_PORT`, `SMTP_EMAIL`, `SMTP_PASSWORD`
- **Algorand Node**:
  - `ALGOD_ADDRESS` (e.g., `https://testnet-api.algonode.cloud`)
  - `INDEXER_ADDRESS` (e.g., `https://testnet-idx.algonode.cloud`)
- **Smart Contract**:
  - `ALGORAND_APP_ID` (The ID of the deployed contract)
- **Wallet Configuration**:
  - `ANCHOR_SENDER` (Funded TestNet wallet address)
  - `ANCHOR_MNEMONIC` (25-word mnemonic)
- **Security**: `USER_HASH_SALT`

## Why Blockchain Is Necessary
A centralized database alone relies entirely on the trust of the database administrator. In a campus setting, this creates conflict of interest.
- **Immutable History**: Once a vote is anchored on Algorand, it cannot be deleted or modified by admins.
- **Verifiable Logic**: The smart contract ensures the rules (deadlines, counting) are executed exactly as written, independent of the backend server's state.
- **Transparency**: Anyone can audit the blockchain transactions to verify the election results match the announced winner.

## Future Improvements
- **Agentic AI Monitoring**: Autonomous agents to monitor admin activity and enforce election time windows.
