import { useState, useEffect, useCallback } from "react";
import { 
    onAuthStateChanged, 
    signInWithEmailAndPassword, 
    signInWithPopup, 
    GoogleAuthProvider,
    signOut,
    updateProfile,
    browserLocalPersistence,
    browserSessionPersistence,
    setPersistence
} from "firebase/auth";
import { auth } from "../config/firebase";
import { API_BASE_URL } from "../config/env";
import { AuthContext } from "./authContextInstance";

function normalizeUser(backendData, firebaseUser) {
    if (!backendData) return null;
    const fullName = backendData.full_name ||
        [backendData.firstName, backendData.lastName].filter(Boolean).join(" ") ||
        firebaseUser?.displayName || "User";
    const avatar = backendData.avatar || firebaseUser?.photoURL || null;

    return {
        ...backendData,
        id: backendData.id || backendData._id || firebaseUser?.uid,
        full_name: fullName,
        displayName: fullName,
        avatar,
        photoURL: avatar,
    };
}

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(null);
    const [loading, setLoading] = useState(true);
    const [authError, setAuthError] = useState(null);

    const fetchUserProfile = useCallback(async (firebaseUser, idToken) => {
        try {
            const res = await fetch(`${API_BASE_URL}/auth/me`, {
                headers: { "Authorization": `Bearer ${idToken}` }
            });

            if (!res.ok) {
                let errDetail = "Session authorization failed.";
                try {
                    const errData = await res.json();
                    errDetail = errData.detail || errData.error || errDetail;
                } catch {}
                setUser(null);
                setAuthError(errDetail);
                return;
            }

            const data = await res.json();
            setUser(normalizeUser(data, firebaseUser));
            setAuthError(null);
        } catch (err) {
            setUser(null);
            setAuthError(err.message || "Could not connect to AuthentiScore server.");
        }
    }, []);

    useEffect(() => {
        const unsubscribe = onAuthStateChanged(auth, async (currentUser) => {
            try {
                if (currentUser) {
                    const t = await currentUser.getIdToken();
                    setToken(t);
                    await fetchUserProfile(currentUser, t);
                } else {
                    setUser(null);
                    setToken(null);
                    setAuthError(null);
                }
            } catch (err) {
                setAuthError(err.message || "Failed to authenticate session");
                setUser(null);
            } finally {
                setLoading(false);
            }
        });

        return () => unsubscribe();
    }, [fetchUserProfile]);

    const login = async (email, password, rememberMe = true) => {
        setAuthError(null);
        await setPersistence(auth, rememberMe ? browserLocalPersistence : browserSessionPersistence);
        return await signInWithEmailAndPassword(auth, email, password);
    };

    const googleLogin = async () => {
        setAuthError(null);
        const provider = new GoogleAuthProvider();
        return await signInWithPopup(auth, provider);
    };

    const logout = async () => {
        setAuthError(null);
        setUser(null);
        setToken(null);
        await signOut(auth);
    };

    const updateUserProfile = async (displayName, photoURL) => {
        if (auth.currentUser) {
            await updateProfile(auth.currentUser, { displayName, photoURL });
            setUser(prev => prev ? {
                ...prev,
                full_name: displayName,
                displayName,
                photoURL,
                avatar: photoURL
            } : null);
        }
    };

    const refreshUser = async () => {
        if (!auth.currentUser) return;
        try {
            const t = await auth.currentUser.getIdToken(true);
            setToken(t);
            await fetchUserProfile(auth.currentUser, t);
        } catch (e) {
            console.error("User refresh error:", e);
        }
    };

    return (
        <AuthContext.Provider value={{ 
            user, 
            token, 
            loading, 
            authError, 
            login, 
            googleLogin, 
            logout, 
            updateUserProfile, 
            refreshUser, 
            setUser,
            retryAuth: refreshUser
        }}>
            {children}
        </AuthContext.Provider>
    );
}

