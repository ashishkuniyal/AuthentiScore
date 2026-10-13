# AuthentiScore Frontend

AuthentiScore is an enterprise-grade AI profile authenticity and bot detection platform. The frontend is built using **React 19**, **Vite**, **Tailwind CSS v4**, and **Firebase Authentication**.

## Getting Started

### Prerequisites
- Node.js 20+
- npm 10+

### Setup
1. Install dependencies:
   ```bash
   npm ci
   ```
2. Configure environment:
   ```bash
   cp .env.example .env
   ```
   Set `VITE_API_URL` (default: `http://localhost:8000`).

3. Start development server:
   ```bash
   npm run dev
   ```

### Quality & Build Commands
- **Lint**: Run fast static analysis via Oxlint (enforced to 0 warnings):
  ```bash
  npm run lint
  ```
- **Build**: Compile production assets:
  ```bash
  npm run build
  ```
- **Preview**: Preview production build locally:
  ```bash
  npm run preview
  ```

## Architecture
- `src/config/`: Centralized API/WS URLs (`env.js`) and Firebase Auth setup (`firebase.js`).
- `src/services/api.js`: Unified API client with automatic Firebase token refresh and 401 retry.
- `src/context/`: Decoupled Auth and Notifications WebSocket contexts with clean Fast Refresh exports.
- `src/utils/`: Single source of truth for risk bands (34/67/90 thresholds), formatting, and toasts.
- `src/components/`: Interactive dashboard, profile scanner, batch CSV processor, audience auditor, and settings.
