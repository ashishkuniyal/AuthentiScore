import { createContext, useContext, useState, useEffect } from "react";
import { 
    onAuthStateChanged, 
    signInWithEmailAndPassword, 
    signInWithPopup, 
    GoogleAuthProvider,
    signOut,
    updateProfile
} from "firebase/auth";
import { auth } from "../config/firebase";
import { setApiAuthToken } from "../services/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const unsubscribe = onAuthStateChanged(auth, async (currentUser) => {
            if (currentUser) {
                // User is signed in via Firebase
                const t = await currentUser.getIdToken();
                setToken(t);
                setApiAuthToken(t);
                
                // Fetch our backend profile using the Firebase token
                try {
                    const res = await fetch("http://localhost:8000/auth/me", {
                        headers: { "Authorization": `Bearer ${t}` }
                    });
                    if (res.ok) {
                        const data = await res.json();
                        setUser(data);
                    } else {
                        // If backend fails to find user, we still have the firebase user
                        // Typically you might auto-provision in the backend here
                        setUser({ email: currentUser.email, full_name: currentUser.displayName || "Firebase User" });
                    }
                } catch (e) {
                    setUser({ email: currentUser.email, full_name: currentUser.displayName || "Firebase User", photoURL: currentUser.photoURL });
                }
            } else {
                setUser(null);
                setToken(null);
                setApiAuthToken(null);
            }
            setLoading(false);
        });

        return () => unsubscribe();
    }, []);

    const login = async (username, password) => {
        // Authenticate with Firebase Email/Password
        await signInWithEmailAndPassword(auth, username, password);
    };

    const googleLogin = async () => {
        // Authenticate with Firebase Google Provider
        const provider = new GoogleAuthProvider();
        await signInWithPopup(auth, provider);
    };

    const logout = async () => {
        await signOut(auth);
    };

    const updateUserProfile = async (displayName, photoURL) => {
        if (auth.currentUser) {
            await updateProfile(auth.currentUser, { displayName, photoURL });
            // Update local state to reflect changes immediately
            setUser(prev => ({
                ...prev,
                full_name: displayName,
                photoURL: photoURL
            }));
        }
    };

    const refreshUser = async () => {
        if (!auth.currentUser) return;
        try {
            const t = await auth.currentUser.getIdToken();
            const res = await fetch("http://localhost:8000/auth/me", {
                headers: { "Authorization": `Bearer ${t}` }
            });
            if (res.ok) {
                const data = await res.json();
                setUser(data);
            }
        } catch (e) {
            console.error(e);
        }
    };

    return (
        <AuthContext.Provider value={{ user, token, loading, login, googleLogin, logout, updateUserProfile, refreshUser, setUser }}>
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => useContext(AuthContext);
