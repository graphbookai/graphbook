import React from "react";
import { notification } from "antd";
import type { NotificationInstance } from "antd/es/notification/interface";

let globalNotificationContext: React.ReactElement<any, string | React.JSXElementConstructor<any>> | null = null;
let globalNotificationCtrl: NotificationInstance | null = null;
export function useNotificationInitializer() {
    const [notificationCtrl, notificationCtxt] = notification.useNotification({ maxCount: 1 });
    globalNotificationContext = notificationCtxt;
    globalNotificationCtrl = notificationCtrl;

    return [notificationCtrl, notificationCtxt];
}

export function useNotification(): NotificationInstance {
    if (!globalNotificationCtrl) {
        throw new Error("Notification context not initialized");
    }

    return globalNotificationCtrl;
}
