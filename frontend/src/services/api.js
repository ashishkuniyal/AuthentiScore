import { API_BASE_URL } from "../config/env";
import { auth } from "../config/firebase";

// ============================================================
// Helper — Handle API / Network Errors
// ============================================================

async function handleResponse(response, defaultMessage) {
    let data = {};
    try {
        data = await response.json();
    } catch {
        data = {};
    }

    if (!response.ok) {
        throw new Error(
            data.detail ||
            data.error ||
            data.message ||
            defaultMessage ||
            `Request failed with status ${response.status}`
        );
    }

    return data;
}

// ============================================================
// Helper — Network Request Wrapper (F2, F4)
// ============================================================

export async function request(url, options = {}, defaultMessage) {
    const headers = { ...(options.headers || {}) };

    // Get fresh token dynamically per request (F2)
    let token = null;
    try {
        if (auth.currentUser) {
            token = await auth.currentUser.getIdToken();
        }
    } catch {
        token = null;
    }

    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }

    // Do NOT set Content-Type if body is FormData (browser must set multipart boundary)
    if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
        headers["Content-Type"] = "application/json";
    }

    options.headers = headers;

    try {
        let response = await fetch(url, options);

        // F2: Retry once on 401 with forced token refresh
        if (response.status === 401 && auth.currentUser) {
            try {
                const refreshedToken = await auth.currentUser.getIdToken(true);
                headers["Authorization"] = `Bearer ${refreshedToken}`;
                options.headers = headers;
                response = await fetch(url, options);
            } catch {
                // If refresh fails, let handleResponse handle error
            }
        }

        return await handleResponse(response, defaultMessage);
    } catch (error) {
        if (error instanceof TypeError) {
            throw new Error(
                "AuthentiScore backend is unavailable. Please make sure the API server is running."
            );
        }
        throw error;
    }
}

// ============================================================
// Scan Endpoints
// ============================================================

export async function validateProfileUrl(profileUrl) {
    return await request(
        `${API_BASE_URL}/scan/validate-url?profile_url=${encodeURIComponent(profileUrl)}`,
        { method: "POST" },
        "Unable to validate profile URL."
    );
}

export async function collectProfile(profileUrl) {
    return await request(
        `${API_BASE_URL}/scan/collect-test?profile_url=${encodeURIComponent(profileUrl)}`,
        { method: "POST" },
        "Unable to collect profile data."
    );
}

export async function autoScan(profileUrl, consent = true) {
    return await request(
        `${API_BASE_URL}/scan/auto`,
        {
            method: "POST",
            body: JSON.stringify({ profile_url: profileUrl, consent })
        },
        "Unable to complete the automated profile scan."
    );
}


export async function profileScan(profile) {
    return await request(
        `${API_BASE_URL}/scan/profile-scan`,
        {
            method: "POST",
            body: JSON.stringify(profile)
        },
        "Unable to complete the profile scan."
    );
}

export async function getScanHistory() {
    return await request(
        `${API_BASE_URL}/history`,
        { method: "GET" },
        "Unable to load scan history."
    );
}

export async function getRecentScans(limit = 5) {
    return await request(
        `${API_BASE_URL}/scan/recent?limit=${limit}`,
        { method: "GET" },
        "Unable to load recent scans."
    );
}

export async function downloadReportPdf(scanId) {
    let token = null;
    try {
        if (auth.currentUser) {
            token = await auth.currentUser.getIdToken();
        }
    } catch {}

    const headers = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch(`${API_BASE_URL}/scan/${scanId}/report.pdf`, { headers });
    if (!res.ok) {
        throw new Error("Failed to download PDF report");
    }
    return await res.blob();
}

// ============================================================
// Analytics & Model Endpoints
// ============================================================

export async function getAnalyticsSummary(days = null) {
    const url = days
        ? `${API_BASE_URL}/analytics/summary?days=${days}`
        : `${API_BASE_URL}/analytics/summary`;

    return await request(url, { method: "GET" }, "Unable to load analytics.");
}

export async function getDashboardSummary() {
    return await request(
        `${API_BASE_URL}/analytics/dashboard-summary`,
        { method: "GET" },
        "Unable to load dashboard summary."
    );
}

export async function getModelMetrics() {
    return await request(
        `${API_BASE_URL}/model/metrics`,
        { method: "GET" },
        "Unable to load model metrics."
    );
}

// ============================================================
// Bulk Scanning Endpoints (F4)
// ============================================================

export async function bulkUpload(file) {
    const formData = new FormData();
    formData.append("file", file);

    return await request(
        `${API_BASE_URL}/bulk/upload`,
        {
            method: "POST",
            body: formData
        },
        "Failed to upload CSV for bulk scan."
    );
}

export async function getBulkJob(jobId) {
    return await request(
        `${API_BASE_URL}/bulk/${jobId}`,
        { method: "GET" },
        "Failed to fetch bulk job status."
    );
}

// ============================================================
// Audience / Influencer Audit Endpoints
// ============================================================

export async function uploadInfluencerCsv(file, targetInfluencer = "Unknown") {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("target_influencer", targetInfluencer);

    return await request(
        `${API_BASE_URL}/audit/influencer/csv`,
        {
            method: "POST",
            body: formData
        },
        "Failed to process audience audit CSV."
    );
}

export async function startLiveAudit(targetInfluencer, platform = "instagram", sampleSize = 10, simulateFallback = false) {
    return await request(
        `${API_BASE_URL}/audit/influencer/live`,
        {
            method: "POST",
            body: JSON.stringify({
                target_influencer: targetInfluencer,
                platform,
                sample_size: sampleSize,
                simulate_fallback: simulateFallback
            })
        },
        "Failed to start live audit."
    );
}

export async function getInstagramSessionStatus() {
    return await request(
        `${API_BASE_URL}/audit/instagram/status`,
        { method: "GET" },
        "Failed to check session status."
    );
}

// ============================================================
// User & Profile Endpoints (F4)
// ============================================================

export async function getUserStats() {
    return await request(`${API_BASE_URL}/users/stats`, { method: "GET" }, "Failed to load user stats.");
}

export async function getActivity() {
    return await request(`${API_BASE_URL}/users/activity`, { method: "GET" }, "Failed to load user activity.");
}

export async function getApiKeys() {
    return await request(`${API_BASE_URL}/users/api-keys`, { method: "GET" }, "Failed to load API keys.");
}

export async function createApiKey(name) {
    return await request(
        `${API_BASE_URL}/users/api-keys`,
        {
            method: "POST",
            body: JSON.stringify({ name })
        },
        "Failed to create API key."
    );
}

export async function revokeApiKey(keyId) {
    return await request(
        `${API_BASE_URL}/users/api-keys/${keyId}`,
        { method: "DELETE" },
        "Failed to revoke API key."
    );
}

export async function getBilling() {
    return await request(`${API_BASE_URL}/users/billing`, { method: "GET" }, "Failed to load billing information.");
}

export async function updateProfile(data) {
    return await request(
        `${API_BASE_URL}/users/profile`,
        {
            method: "PUT",
            body: JSON.stringify(data)
        },
        "Failed to update profile."
    );
}

export async function updatePreferences(data) {
    return await request(
        `${API_BASE_URL}/users/preferences`,
        {
            method: "PUT",
            body: JSON.stringify(data)
        },
        "Failed to update preferences."
    );
}

export async function updateNotifications(data) {
    return await request(
        `${API_BASE_URL}/users/notifications`,
        {
            method: "PUT",
            body: JSON.stringify(data)
        },
        "Failed to update notification settings."
    );
}

// ============================================================
// Scanner V2 — Jobs, Feedback, Overrides & Status (B1–B9)
// ============================================================

export async function createScanJob({ input, platform = "instagram", consent = true, force_refresh = false }) {
    return await request(
        `${API_BASE_URL}/scan/jobs`,
        {
            method: "POST",
            body: JSON.stringify({ input, platform, consent, force_refresh })
        },
        "Unable to start background profile analysis job."
    );
}

export async function getScanJob(jobId) {
    return await request(
        `${API_BASE_URL}/scan/jobs/${jobId}`,
        { method: "GET" },
        "Unable to check scan job status."
    );
}

export async function cancelScanJob(jobId) {
    return await request(
        `${API_BASE_URL}/scan/jobs/${jobId}`,
        { method: "DELETE" },
        "Unable to cancel scan job."
    );
}

export async function submitScanFeedback(scanId, { user_verdict, comment = null, rating = null }) {
    return await request(
        `${API_BASE_URL}/scan/${scanId}/feedback`,
        {
            method: "POST",
            body: JSON.stringify({ user_verdict, comment, rating })
        },
        "Failed to record scan feedback."
    );
}

export async function deleteScan(scanId) {
    return await request(
        `${API_BASE_URL}/scan/${scanId}`,
        { method: "DELETE" },
        "Failed to delete scan record."
    );
}

export async function manuallyCompleteScan(scanId, overrides) {
    return await request(
        `${API_BASE_URL}/scan/${scanId}/complete`,
        {
            method: "POST",
            body: JSON.stringify(overrides)
        },
        "Failed to submit manual profile completion."
    );
}

export async function getSystemStatus() {
    return await request(
        `${API_BASE_URL}/system/status`,
        { method: "GET" },
        "Unable to load real-time system status."
    );
}