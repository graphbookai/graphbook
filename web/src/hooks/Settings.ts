import { useState, useEffect, useCallback } from "react";

let settings = {
    theme: "Light",
    graphServerHost: "localhost:8005",
    mediaServerHost: "localhost:8006",
};

const storedSettings = localStorage.getItem('settings');
if (storedSettings) {
    Object.assign(settings, JSON.parse(storedSettings));
}

let localSetters: Function[] = [];

export function useSettings(): [any, (name: string, value: any) => void] {
    const [_, setSettings] = useState(settings);

    const setSetting = (name, value) => {
        settings = {
            ...settings,
            [name]: value
        };
        localStorage.setItem('settings', JSON.stringify(settings));
        for (const setter of localSetters) {
            setter(settings);
        }
    };

    useEffect(() => {
        localSetters.push(setSettings);
        return () => {
            localSetters = localSetters.filter((setter) => setter !== setSettings);
        };
    }, [setSettings]);

    return [settings, setSetting];
}
