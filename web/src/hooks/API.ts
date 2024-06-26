import { API, ServerAPI } from "../api";
import { useState, useEffect } from "react";

let globalAPI: ServerAPI | null = null;
let localSetters: Function[] = [];
let initialized = false;

const initialize = () => setGlobalAPI(API);
const disable = () => setGlobalAPI(null);

export function useAPI() {
    const [_, setAPI] = useState<ServerAPI | null>(globalAPI);

    useEffect(() => {
        if (!initialized) {
            API.addWsEventListener('open', initialize);
            API.addWsEventListener('close', disable);
            initialized = true;
        }
        return () => {
            if (localSetters.length === 0) {
                API.removeWsEventListener('open', initialize);
                API.removeWsEventListener('close', disable);
                initialized = false;
            }
        }
    }, []);

    useEffect(() => {
        localSetters.push(setAPI);
        return () => {
            localSetters = localSetters.filter((setter) => setter !== setAPI);
        };
    }, []);

    return globalAPI;
}

function setGlobalAPI(api: ServerAPI | null) {
    globalAPI = api;
    for (const setter of localSetters) {
        setter(globalAPI);
    }
}
