import { useContext } from "react";
import { NotificationsContext } from "./notificationsContextInstance";

export function useNotifications() {
    return useContext(NotificationsContext);
}
