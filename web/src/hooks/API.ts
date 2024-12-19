import { API, ServerAPI } from "../api";
import { useState, useEffect, useCallback } from "react";
import { getGlobalRunningFile } from "./RunState";

let globalAPI: ServerAPI | null = null;
let localSetters: Function[] = [];
let initialized = false;

const onConnectStateChange = (isConnected: boolean) => {
    if (!isConnected) {
        setGlobalAPI(null);
    } else {
        setGlobalAPI(API);
    }
};

function setGlobalAPI(api: ServerAPI | null) {
    globalAPI = api;
    for (const setter of localSetters) {
        setter(globalAPI);
    }
}

export function useAPI() {
    const [_, setAPI] = useState<ServerAPI | null>(globalAPI);

    useEffect(() => {
        if (!initialized) {
            initialized = true;
            const discard = API.onConnectStateChange(onConnectStateChange);

            return () => {
                discard();
                initialized = false
            };
        }
    }, []);

    useEffect(() => {
        localSetters.push(setAPI);

        return () => {
            localSetters = localSetters.filter((setter) => setter !== setAPI);
        }
    }, []);

    return globalAPI;
}

let apiMessageCallbacks: { [event_type: string]: Function[] } = {};
let apiSetTo: ServerAPI | null = null;
export function useAPIMessage(event_type: string, callback: Function) {
    const api = useAPI();

    useEffect(() => {
        if(api && api !== apiSetTo) {
            apiSetTo = api;
            const globalListener = (res) => {
                const msg = JSON.parse(res.data);
                if (apiMessageCallbacks[msg.type]) {
                    apiMessageCallbacks[msg.type].forEach((cb) => cb(msg.data));
                }
            };
            api.addWSMessageListener(globalListener);
        }
    }, [api]);

    useEffect(() => {
        if (!apiMessageCallbacks[event_type]) {
            apiMessageCallbacks[event_type] = [];
        }
        apiMessageCallbacks[event_type].push(callback);

        return () => {
            apiMessageCallbacks[event_type] = apiMessageCallbacks[event_type].filter((cb) => cb !== callback);
        };
    }, []);
}

export function useAPINodeMessage(event_type: string, node_id: string, filename: string, callback: Function) {
    useAPIMessage(event_type, useCallback((msg) => {
        if (filename === getGlobalRunningFile() && msg[node_id]) {
            callback(msg[node_id]);
        }
    }, [node_id, callback, filename]));
}


let localReconnectListeners: Function[] = [];
let reconnectInitialized = false;
let timeUntilReconnect = 0;
export function useAPIReconnectTimer() {
    const [_, reconnectTime] = useState<number>(timeUntilReconnect);

    const onTimerChanged = (time: number) => {
        timeUntilReconnect = time;
        for (const listener of localReconnectListeners) {
            listener(time);
        }
    };

    useEffect(() => {
        if (!reconnectInitialized) {

            const discard = API.onReconnectTimerChange(onTimerChanged);
            reconnectInitialized = true;

            return () => {
                discard();
                reconnectInitialized = false;
            };
        }
    });

    useEffect(() => {
        localReconnectListeners.push(reconnectTime);

        return () => {
            localReconnectListeners = localReconnectListeners.filter((listener) => listener !== reconnectTime);
        }
    }, []);

    return timeUntilReconnect;
}
