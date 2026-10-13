import { createContext } from "react";

export const NotificationsContext = createContext({
    notifications: [],
    lastAuditMessage: null,
    clearNotifications: () => {}
});
