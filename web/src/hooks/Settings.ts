import { useState, useEffect, useCallback } from "react";

const MONITOR_DATA_COLUMNS = ['stats', 'logs', 'notes', 'images'];
let settings = {
    theme: "Light",
    disableTooltips: false,
    graphServerHost: "localhost:8005",
    mediaServerHost: "localhost:8006",
    useExternalMediaServer: false,
    monitorDataColumns: MONITOR_DATA_COLUMNS,
    monitorLogsShouldScrollToBottom: true,
    quickviewImageHeight: 100,
    nodeTabsDisplay: "BOTH",
};

const storedSettings = localStorage.getItem('settings');
if (storedSettings) {
    Object.assign(settings, JSON.parse(storedSettings));
}

let localSetters: Function[] = [];

export function useSettings(): [any, (name: string, value: any) => void] {
    const [_, setSettings] = useState(settings);

    const setSetting = useCallback((name, value) => {
        settings = {
            ...settings,
            [name]: value
        };
        localStorage.setItem('settings', JSON.stringify(settings));
        for (const setter of localSetters) {
            setter(settings);
        }
    }, [settings, localSetters]);

    useEffect(() => {
        localSetters.push(setSettings);
        return () => {
            localSetters = localSetters.filter((setter) => setter !== setSettings);
        };
    }, [setSettings]);

    return [settings, setSetting];
}
