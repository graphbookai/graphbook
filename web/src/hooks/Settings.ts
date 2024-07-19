import { useState, useEffect, useCallback } from "react";

const MONITOR_DATA_COLUMNS = ['stats', 'logs', 'notes', 'images'];
let settings = {
    theme: "Light",
    graphServerHost: "localhost:8005",
    mediaServerHost: "localhost:8006",
    monitorDataColumns: MONITOR_DATA_COLUMNS,
    monitorLogsShouldScrollToBottom: true,
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
