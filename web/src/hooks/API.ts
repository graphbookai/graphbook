import { API, ServerAPI } from "../api";
import { useState, useEffect, useCallback } from "react";

type States = { [type: string]: any };
type GraphStateLists = { [graph: string]: States };
type StateCallbacks = { [type: string]: Function[] };
type GraphStateCallbacks = { [graph: string]: StateCallbacks };

let globalAPI: ServerAPI | null = null;
let initialized = false;
let apiSetters: Function[] = [];

const messageStates: GraphStateLists = {};
const messageStateListeners: GraphStateCallbacks = {};
const lastValueSetters: GraphStateCallbacks = {};

const globalMessageStates: States = {};
const globalMessageListeners: StateCallbacks = {};
const globalLastValueSetters: StateCallbacks = {};
const everyGraphLastValueSetters: StateCallbacks = {};
const everyGraphMessageListeners: StateCallbacks = {};


const onConnectStateChange = (isConnected: boolean) => {
    const setGlobalAPI = (api: ServerAPI | null) => {
        globalAPI = api;
        for (const setter of apiSetters) {
            setter(globalAPI);
        }
    }

    const clearGraphs = () => {
        for (const graph in messageStates) {
            for (const type in messageStates[graph]) {
                delete messageStates[graph][type];
            }
        }
    }

    if (!isConnected) {
        setGlobalAPI(null);
    } else {
        clearGraphs();
        setGlobalAPI(API);
    }
};

function onStatefulMessage(msg) {
    const parsedMsg = JSON.parse(msg.data);

    let states = globalMessageStates;
    let listeners = globalMessageListeners;
    let setters = globalLastValueSetters;
    const { graph_id, type, data } = parsedMsg;

    if (graph_id) {
        states = messageStates[graph_id];
        listeners = messageStateListeners[graph_id];
        setters = lastValueSetters[graph_id];
        if (!states) {
            states = { [type]: data };
            messageStates[graph_id] = states;
        }
        if (!listeners) {
            listeners = { [type]: [] };
            messageStateListeners[graph_id] = listeners;
        }
        if (!setters) {
            setters = { [type]: [] };
            lastValueSetters[graph_id] = setters;
        }
    }

    states[type] = data;
    if (listeners[type]) {
        for (const listener of listeners[type]) {
            listener(data);
        }
    }
    if (setters[type]) {
        for (const setter of setters[type]) {
            setter(data);
        }
    }
    if (everyGraphLastValueSetters[type]) {
        for (const setter of everyGraphLastValueSetters[type]) {
            setter(data);
        }
    }
    if (everyGraphMessageListeners[type]) {
        const everyState = Object.entries(messageStates).reduce((acc, [graph, states]) => {
            if (states[type]) {
                acc[graph] = states[type];
            }
            return acc;
        }, {});
        for (const listener of everyGraphMessageListeners[type]) {
            listener(everyState);
        }
    }
}

export function useAPI() {
    const [_, setAPI] = useState<ServerAPI | null>(globalAPI);

    useEffect(() => {
        if (!initialized) {
            initialized = true;
            const discard = API.onConnectStateChange(onConnectStateChange);
            API.addWSMessageListener(onStatefulMessage)

            return () => {
                discard();
                API.removeWSMessageListener(onStatefulMessage);
                initialized = false
            };
        }
    }, []);

    useEffect(() => {
        apiSetters.push(setAPI);

        return () => {
            apiSetters = apiSetters.filter((setter) => setter !== setAPI);
        }
    }, []);

    return globalAPI;
}

export function useAPIMessageEffect(event_type: string, callback: Function, graph: string | null = null) {
    useEffect(() => {
        if (graph) {
            if (!messageStateListeners[graph]) {
                messageStateListeners[graph] = { [event_type]: [] };
            }
            
            if (!messageStateListeners[graph][event_type]) {
                messageStateListeners[graph][event_type] = [];
            }

            messageStateListeners[graph][event_type].push(callback);
            return () => {
                messageStateListeners[graph][event_type] = messageStateListeners[graph][event_type].filter((cb) => cb !== callback);
            };
        }

        if (!globalMessageListeners[event_type]) {
            globalMessageListeners[event_type] = [];
        }

        globalMessageListeners[event_type].push(callback);
        return () => {
            globalMessageListeners[event_type] = globalMessageListeners[event_type].filter((cb) => cb !== callback);
        }
    }, []);
}

export function useAPINodeMessageEffect(event_type: string, node_id: string, graph_id: string, callback: Function) {
    const internalCallback = useCallback((msg) => {
        if (msg[node_id]) {
            callback(msg[node_id]);
        }
    }, [node_id, callback]);

    useAPIMessageEffect(event_type, internalCallback, graph_id);
}

export function useAPIMessageLastValue(event_type: string, graph: string | null = null): any | undefined {
    const [_, setState] = useState<any>(null);

    useEffect(() => {
        if (graph) {
            let graphSetters = lastValueSetters[graph];
            if (!graphSetters) {
                graphSetters = { [event_type]: [] };
                lastValueSetters[graph] = graphSetters;
            } else if (!graphSetters[event_type]) {
                graphSetters[event_type] = [];
            }
            graphSetters[event_type].push(setState);

            return () => {
                graphSetters[event_type] = graphSetters[event_type].filter((cb) => cb !== setState);
            }
        }

        if (!globalLastValueSetters[event_type]) {
            globalLastValueSetters[event_type] = [];
        }
        globalLastValueSetters[event_type].push(setState);

        return () => {
            globalLastValueSetters[event_type] = globalLastValueSetters[event_type].filter((cb) => cb !== setState);
        }
    }, []);

    let states = globalMessageStates;
    if (graph) {
        states = messageStates[graph];
    }

    return states?.[event_type];
}

export function useAPIEveryGraphLastValue(event_type: string) {
    const [_, setState] = useState<any>(null);

    useEffect(() => {
        if (!everyGraphLastValueSetters[event_type]) {
            everyGraphLastValueSetters[event_type] = [];
        }
        everyGraphLastValueSetters[event_type].push(setState);

        return () => {
            everyGraphLastValueSetters[event_type] = everyGraphLastValueSetters[event_type].filter((cb) => cb !== setState);
        };
    }, []);

    return Object.entries(messageStates).reduce((acc, [graph, states]) => {
        if (states[event_type]) {
            acc[graph] = states[event_type];
        }
        return acc;
    }, {});
}


export function useAPIEveryGraphMessageEffect(event_type: string, callback: Function) {
    useEffect(() => {
        if (!everyGraphMessageListeners[event_type]) {
            everyGraphMessageListeners[event_type] = [];
        }
        everyGraphMessageListeners[event_type].push(callback);

        return () => {
            everyGraphMessageListeners[event_type] = everyGraphMessageListeners[event_type].filter((cb) => cb !== callback);
        };
    }, []);
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
