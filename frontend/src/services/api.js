const API_BASE_URL = "http://127.0.0.1:8000";


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
            defaultMessage
        );
    }

    return data;
}


let authToken = null;

export function setApiAuthToken(token) {
    authToken = token;
}

// ============================================================
// Helper — Network Error Wrapper
// ============================================================

async function request(url, options = {}, defaultMessage) {
    const headers = options.headers || {};
    if (authToken) {
        headers["Authorization"] = `Bearer ${authToken}`;
    }
    options.headers = headers;

    try {
        const response = await fetch(url, options);
        return await handleResponse(response, defaultMessage);

    } catch (error) {

        // Backend is unreachable
        if (
            error instanceof TypeError &&
            error.message.toLowerCase().includes("fetch")
        ) {

            throw new Error(
                "AuthentiScore backend is unavailable. Please make sure the API server is running."
            );
        }

        // Preserve our own useful API errors
        throw error;
    }
}


// ============================================================
// Validate Profile URL
// ============================================================

export async function validateProfileUrl(profileUrl) {

    return await request(

        `${API_BASE_URL}/scan/validate-url?profile_url=${encodeURIComponent(
            profileUrl
        )}`,

        {
            method: "POST",

            headers: {
                "Content-Type": "application/json"
            }
        },

        "Unable to validate profile URL."
    );
}


// ============================================================
// Collect permitted public profile data
// ============================================================

export async function collectProfile(profileUrl) {

    return await request(

        `${API_BASE_URL}/scan/collect-test?profile_url=${encodeURIComponent(
            profileUrl
        )}`,

        {
            method: "POST",

            headers: {
                "Content-Type": "application/json"
            }
        },

        "Unable to collect permitted profile data."
    );
}


// ============================================================
// Automated URL-driven scan (primary flow)
// ============================================================
//
// Single request: URL → collection → ML+NLP → risk → SHAP → result.
// The backend performs all pipeline steps internally.
//
// On success: returns a complete AutoScanResponse including
//   collection metadata (source, status, fields_collected).
// On partial/failed collection: response still contains
//   whatever was collected and collection.status = "partial"|"failed",
//   so the frontend can show the manual fallback pre-filled.

export async function autoScan(profileUrl) {

    return await request(

        `${API_BASE_URL}/scan/auto`,

        {
            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({ profile_url: profileUrl })
        },

        "Unable to complete the automated profile scan."
    );
}


// ============================================================
// Run complete persisted profile scan
// ============================================================

export async function profileScan(profile) {

    return await request(

        `${API_BASE_URL}/scan/profile-scan`,

        {
            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify(profile)
        },

        "Unable to complete the profile scan."
    );
}


// ============================================================
// Get Scan History
// ============================================================

export async function getScanHistory() {

    return await request(

        `${API_BASE_URL}/history`,

        {
            method: "GET",

            headers: {
                "Content-Type": "application/json"
            }
        },

        "Unable to load scan history."
    );
}


// ============================================================
// Get Analytics Summary
// ============================================================

export async function getAnalyticsSummary(days = null) {
    
    const url = days 
        ? `${API_BASE_URL}/analytics/summary?days=${days}` 
        : `${API_BASE_URL}/analytics/summary`;

    return await request(
        url,

        {
            method: "GET",

            headers: {
                "Content-Type": "application/json"
            }
        },

        "Unable to load analytics."
    );
}

// ============================================================
// Get Dashboard Summary
// ============================================================

export async function getDashboardSummary() {
    return await request(
        `${API_BASE_URL}/analytics/dashboard-summary`,
        {
            method: "GET",
            headers: {
                "Content-Type": "application/json"
            }
        },
        "Unable to load dashboard summary."
    );
}

// ============================================================
// Get Recent Scans
// ============================================================

export async function getRecentScans(limit = 5) {
    return await request(
        `${API_BASE_URL}/scan/recent?limit=${limit}`,
        {
            method: "GET",
            headers: {
                "Content-Type": "application/json"
            }
        },
        "Unable to load recent scans."
    );
}

// ============================================================
// Upload Influencer CSV for Audit
// ============================================================

export async function uploadInfluencerCsv(file, targetInfluencer = "Unknown") {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("target_influencer", targetInfluencer);

    try {
        const response = await fetch(`${API_BASE_URL}/audit/influencer/csv`, {
            method: "POST",
            body: formData,
        });
        
        let data = {};
        try { data = await response.json(); } catch {}
        
        if (!response.ok) throw new Error(data.detail || data.error || "Failed to process audit.");
        return data;
    } catch (error) {
        throw error;
    }
}

// ============================================================
// Start Live Influencer Audit (Background Task)
// ============================================================

export async function startLiveAudit(targetInfluencer, platform = "instagram", sampleSize = 10, simulateFallback = false) {
    return await request(
        `${API_BASE_URL}/audit/influencer/live`,
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                target_influencer: targetInfluencer,
                platform: platform,
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