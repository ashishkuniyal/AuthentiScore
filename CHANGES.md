# AuthentiScore — Remediation & Implementation Changelog

This document tracks all fixes, refactorings, security hardenings, and architectural updates completed in AuthentiScore, categorized by phase and item identifier.

---

## Decisions Taken (D1–D12)

| # | Decision | Chosen Resolution & Details |
|---|----------|----------------------------|
| **D1** | Risk bands | **34 / 67 / 90**: Standardized single source of truth across backend (`app/core/risk_levels.py`) and frontend (`src/utils/risk.js`). Low: `< 34`, Medium: `34–66`, High: `67–89`, Very High: `≥ 90`. |
| **D2** | `email_verified` for password accounts | **Enforced**: Unverified password accounts are rejected with 401. OAuth/Google accounts inherit verification from identity provider. |
| **D3** | Simulated network/image forensics | **Hidden by default**: Network graph and image noise forensics are suppressed unless explicitly enabled via `ENABLE_SIMULATED_FORENSICS=true`. When simulated data is shown, a "Simulated demo data" badge is displayed. |
| **D4** | API keys | **CRUD maintained**: Key creation and revocation endpoints work securely with hashing. UI displays active keys and indicates Enterprise tiering. |
| **D5** | Forward Instagram session to Apify | **No**: User Instagram sessions are never forwarded to third-party Apify actors. |
| **D6** | Apify enrichment of follower samples | **Off (`APIFY_ENRICH=false`)**: Basic follower sampling is performed without aggressive deep enrichment to minimize cost and latency. |
| **D7** | Twitter public-HTML scraper | **Deleted**: Broken HTML scraping fallback removed; requests route to Twitter API v2 or graceful insufficient data handling. |
| **D8** | Scraper retry / UA rotation | **Single honest request**: Single standard request with one retry on timeout/5xx, using clean descriptive headers. |
| **D9** | SMOTE vs Class-Weighting | **Class-weighted variant selected**: Variant 2 trained with balanced class weights achieved a lower test Brier score (0.0667 vs 0.0677) and lower cross-dataset Brier score (0.0686 vs 0.0712) without distorting posterior calibration probabilities. |
| **D10** | Broad keywords / negative sentiment boost | **Documented & flagged**: Retained with bounded influence; documented in model limitations. |
| **D11** | Minimum observed inputs for scoring | **4 of 6 required**: Must observe at least 4 of the 6 core profile fields, including `followers` and `following`. Below this threshold, profile receives `Insufficient Data` without hallucinating defaults. |
| **D12** | Data retention window | **30 days (`SCAN_RETENTION_DAYS=30`)**: Configurable TTL applied to historical scans and job records. |

---

## Phase 0: Blockers (B1–B6)

- **B1**: Pinned and reconciled all dependencies across `backend/requirements.txt`, `backend/requirements-dev.txt`, and `backend/requirements-train.txt`. Added `mongomock` for hermetic testing.
- **B2**: Implemented lazy model loader in `backend/app/services/model_store.py` (`get_model()`, `get_features()`, `get_metrics()`, `is_loaded()`). Application boots and serves `/health` even when model `.pkl` files are not present.
- **B3**: Fixed MongoDB initialization in `backend/app/database/mongodb.py`. Removed import-time pings and replaced blocking startup with non-blocking async `setup_indexes()` in FastAPI lifespan.
- **B4**: Created comprehensive `.env.example` templates for both backend and frontend documenting all environment variables.
- **B5**: Cleaned project documentation, clarified setup steps, verified licensing, and removed references to missing directories.
- **B6**: Removed all lingering references to obsolete `authentiscore_rf_v1.pkl` and `train_v2_ensemble.py`.

---

## Phase 1: Security (S1–S15)

- **S1**: Removed custom JWT decoder and unsafe unsigned token handling. Integrated Firebase Admin SDK token verification (`verify_id_token()`).
- **S2**: Fixed role escalation privilege bug: admin role is strictly assigned based on server-side `ADMIN_EMAILS` whitelist, preventing self-assigned roles.
- **S3**: Added explicit authentication dependencies (`get_current_user`) across protected routes (`/scan`, `/bulk`, `/audit`, `/analytics`, `/users`, `/history`).
- **S4**: Implemented ownership checks on scans and reports, preventing users from accessing or downloading other users' audit reports.
- **S5**: Secured WebSocket endpoint `/ws/notifications`: requires valid token in query param (`?token=...`), rejects invalid tokens with 4401 closure, and routes events strictly to authenticated user IDs.
- **S6**: Secured and isolated temporary file storage.
- **S7**: Prevented SSRF in URL validation by validating protocols and prohibiting private/loopback IP targets.
- **S8**: Added rate limiting safeguards on scanning endpoints.
- **S9**: Enforced 1MB maximum payload limits on CSV upload endpoints (`/bulk/upload`, `/audit/influencer/csv`).
- **S10**: Hardened password and API key storage: API keys stored as salted SHA-256 hashes.
- **S11**: Prevented environment variable overrides by setting `load_dotenv(override=False)`.
- **S12**: Made CORS origins strictly configurable via `CORS_ORIGINS` environment variable.
- **S13**: Hardened error messages across endpoints to prevent internal stack trace leakage.
- **S14**: Disabled debug endpoints when `ENABLE_DEBUG_ENDPOINTS=false`.
- **S15**: Added formula injection protection to CSV exports in `BulkScannerPage.jsx`, prepending single quotes to cells starting with `=`, `+`, `-`, or `@`.

---

## Phase 2: Backend Correctness (C1–C36)

- **C1**: Implemented thread-safe WebSocket dispatch via `notify_user_threadsafe()` using event loop tracking.
- **C2**: Added `audit_id` tracking to all audience audit WebSocket events.
- **C3**: Added dead socket cleanup and connection pruning to `ConnectionManager`.
- **C4**: Standardized `Insufficient Data` response shape and status across scan, bulk, and audit pipelines.
- **C5**: Centralized risk bands (34/67/90) in `backend/app/core/risk_levels.py`.
- **C6**: Preserved supplied `bio_length` and `username_digit_ratio` when explicitly provided.
- **C7**: Enforced minimum observed feature count (4 of 6, including followers and following).
- **C8**: Incremented download counter on report retrieval.
- **C9**: Normalized profile URLs consistently across scrapers.
- **C10**: Handled missing numeric fields safely with median imputation rather than zero-forcing.
- **C11**: Implemented honest error reporting on scraper failures.
- **C12**: Ensured fallback collector is invoked with error preserved if primary instaloader fails.
- **C13**: Normalized usernames and handles across all collector inputs.
- **C14**: Apify collector returns `None` for missing/unobserved fields instead of fabricated values.
- **C15**: Unified social platform identifiers across collector routing.
- **C16**: Sanitized bio texts (converting escaped newlines and removing control characters).
- **C17**: Handled private profile metadata gracefully without failing scans.
- **C18**: Cleaned up scraper sessions on failure.
- **C19**: Replaced zero-imputation in training pipeline with `SimpleImputer(strategy='median')`.
- **C20**: Reconciled `calculate_profile_completeness()` into a single shared function used in both training and serving.
- **C21**: Removed `account_age_days` from production features due to absence in public live scrapes.
- **C22**: Strictly cast all explainer booleans to Python `bool` and floats to Python `float`, preventing BSON serialization crashes (`numpy.bool_` / `numpy.float64`). Handled NaN and Inf values.
- **C23**: Verified and aligned SHAP factor direction labels with actual risk impacts.
- **C24**: Added explanation method approximation tags.
- **C25**: Bounded sentiment score influence in unified risk score combination.
- **C26**: Standardized NLP signal categories and threshold definitions.
- **C27**: Cleaned up temporary PDF files and memory buffers after generation.
- **C28**: Bulk processor decodes UTF-8 BOM, validates header row, saves individual scan records, and finishes in a `try...finally` block to prevent stuck jobs.
- **C29**: Implemented 10-minute cache on Apify Instagram session validation.
- **C30**: Lifespan startup handles MongoDB indexes asynchronously without blocking worker thread boot.
- **C31**: `/health` endpoint checks database connectivity and returns 503 degraded status on disconnection.
- **C32**: Added `model_store` constants and `/model/metrics` endpoint serving `metrics_v3.json`.
- **C33**: Aligned user statistics calculation with standardized risk bands.
- **C34**: Ensured activity log timestamps are timezone-aware ISO 8601 strings.
- **C35**: Hardened background task exceptions with structured error logging.
- **C36**: Verified FastAPI Query parameter handling when called programmatically.

---

## Phase 3: Frontend (F1–F14)

- **F1**: Unified API and WebSocket host resolution in `frontend/src/config/env.js`.
- **F2**: Implemented dynamic Firebase token retrieval and automatic 401 retry with `getIdToken(true)` in `frontend/src/services/api.js`.
- **F3**: Normalized user auth object; fixed `googleLogin` hook usage and `rememberMe` persistence.
- **F4**: Routed all raw `fetch()` calls across components (`ProfilePage`, `ResultsPanel`, `HistoryPage`, `BulkScannerPage`, `InfluencerAuditPage`) through `api.js`.
- **F5**: Centralized risk bands and styling in `frontend/src/utils/risk.js` (34/67/90 thresholds).
- **F6**: Wired real model metrics (accuracy 90.7%, ROC-AUC 0.971) from `/model/metrics` into `DashboardOverview.jsx`, replaced mock sparklines with real trends, and used `Promise.allSettled`.
- **F7**: Implemented single authenticated WebSocket stream in `NotificationsContext.jsx`; `InfluencerAuditPage.jsx` listens via `useNotifications()` filtered by `audit_id`.
- **F8**: Hardened `BulkScannerPage.jsx`: polling terminates on terminal states; CSV export protected against formula injection.
- **F9**: Standardized PDF report download using `downloadReportPdf()` with DOM-attached anchor and `setTimeout(revoke, 1000)`.
- **F10**: Updated manual fallback form in `ScannerPage.jsx`: required explicit user selection for profile picture and privacy status instead of assuming defaults.
- **F11**: Handled `null` scores and signals safely across all widgets; added "Simulated demo data" badge when `simulated === true`.
- **F12**: Replaced swallowed errors in `ProfilePage.jsx` with toast notifications; used `useCallback` loaders.
- **F13**: Eliminated all 43 Oxlint warnings to reach **0 warnings and 0 errors** across all 29 frontend files. Decoupled hooks into `useAuth.js` and `useNotifications.js` for Fast Refresh compliance. Deleted unused `Navbar.jsx` and `jwt-decode`.
- **F14**: Production build succeeds cleanly (`npm run build` in 494ms).

---

## Phase 4: ML, Notebooks, Tests, Docs (M1–M5)

- **M1**: Trained calibrated ensemble `v3` with median imputer, evaluated SMOTE vs class-weighting, exported `authentiscore_ensemble_v3.pkl`, `authentiscore_features_v3.json`, and `metrics_v3.json`. Deleted obsolete `train_v2_ensemble.py`.
- **M2**: Cleaned hardcoded absolute paths across all 26 Jupyter notebooks; cleared large outputs from `M5_EDA.ipynb`.
- **M3**: Built hermetic test suite in `backend/tests/conftest.py` with synthetic model fixture and `mongomock`. Added 14 regression tests in `test_regression.py`. All **80 backend tests pass** with no external network, live MongoDB, or pkl files.
- **M4**: Created GitHub Actions CI pipeline in `.github/workflows/ci.yml` running backend pytest and frontend lint/build.
- **M5**: Updated project `README.md`, `backend/.env.example`, `frontend/README.md`, created `LICENSE` (Apache 2.0), and added full limitations section.
