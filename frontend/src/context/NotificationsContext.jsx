import { useState, useEffect, useRef, useCallback } from "react";
import { WS_BASE_URL } from "../config/env";
import { useAuth } from "./useAuth";
import { NotificationsContext } from "./notificationsContextInstance";

export function NotificationsProvider({ children }) {
    const { user, token } = useAuth();
    const [notifications, setNotifications] = useState([]);
    const [lastAuditMessage, setLastAuditMessage] = useState(null);
    const wsRef = useRef(null);
    const reconnectTimerRef = useRef(null);
    const reconnectAttemptsRef = useRef(0);
    const connectRef = useRef(null);

    const connect = useCallback(() => {
        if (!user || !token) {
            if (wsRef.current) {
                wsRef.current.close();
                wsRef.current = null;
            }
            return;
        }

        if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
            return;
        }

        try {
            const socketUrl = `${WS_BASE_URL}/ws/notifications?token=${encodeURIComponent(token)}`;
            const ws = new WebSocket(socketUrl);
            wsRef.current = ws;

            ws.onopen = () => {
                reconnectAttemptsRef.current = 0;
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data?.type?.startsWith("AUDIT_")) {
                        setLastAuditMessage(data);
                    }
                    setNotifications(prev => [data, ...prev].slice(0, 50));
                } catch (err) {
                    console.warn("Could not parse WS event:", err);
                }
            };

            ws.onclose = (event) => {
                wsRef.current = null;
                // If closed with auth failure (4401), do not attempt aggressive reconnect
                if (event.code === 4401) {
                    console.warn("WebSocket authentication rejected.");
                    return;
                }

                if (user) {
                    const timeout = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
                    reconnectAttemptsRef.current += 1;
                    reconnectTimerRef.current = setTimeout(() => {
                        if (connectRef.current) {
                            connectRef.current();
                        }
                    }, timeout);
                }
            };

            ws.onerror = () => {
                try {
                    ws.close();
                } catch {}
            };
        } catch (e) {
            console.warn("Failed to open WebSocket:", e);
        }
    }, [user, token]);

    useEffect(() => {
        connectRef.current = connect;
    }, [connect]);

    useEffect(() => {
        connect();

        return () => {
            if (reconnectTimerRef.current) {
                clearTimeout(reconnectTimerRef.current);
            }
            if (wsRef.current) {
                wsRef.current.close();
                wsRef.current = null;
            }
        };
    }, [connect]);

    const clearNotifications = useCallback(() => {
        setNotifications([]);
    }, []);

    return (
        <NotificationsContext.Provider value={{ notifications, lastAuditMessage, clearNotifications }}>
            {children}
        </NotificationsContext.Provider>
    );
}
