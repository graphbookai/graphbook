import { API, ServerAPI } from "../api";
import { useState, useEffect, useCallback } from "react";
import { LogEntry } from "../utils";

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

// Centralized logs store
type LogsStore = {
    [graph_id: string]: {
        [node_id: string]: LogEntry[];
    }
};
const logsStore: LogsStore = {};
const logUpdateListeners: { [graph_id: string]: { [node_id: string]: Function[] } } = {};

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
        // Clear logs when connection state changes
        for (const graph in logsStore) {
            delete logsStore[graph];
        }
    }

    if (!isConnected) {
        setGlobalAPI(null);
    } else {
        clearGraphs();
        setGlobalAPI(API);
    }
};

let force = 0;
function onStatefulMessage(msg) {
    const parsedMsg = JSON.parse(msg.data);

    let states = globalMessageStates;
    let listeners = globalMessageListeners;
    let setters = globalLastValueSetters;
    const { graph_id, type, data } = parsedMsg;

    // Special handling for logs type
    if (type === 'logs' && graph_id) {
        handleLogMessage(graph_id, data);
        return;
    }

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
            setter(force++);
        }
    }
    if (everyGraphLastValueSetters[type]) {
        for (const setter of everyGraphLastValueSetters[type]) {
            setter(force++);
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

function handleLogMessage(graph_id: string, logs: LogEntry[]) {
    if (!Array.isArray(logs) || logs.length === 0) return;

    // Initialize graph logs store if needed
    if (!logsStore[graph_id]) {
        logsStore[graph_id] = {};
    }

    const graphLogs = logsStore[graph_id];

    // Process each log entry
    for (const log of logs) {
        const { node_id } = log;
        
        if (node_id) {
            // Add to node-specific logs
            if (!graphLogs[node_id]) {
                graphLogs[node_id] = [];
            }
            
            // If this node has a wipe, and we're processing the first log after a wipe,
            // clear the logs for this node
            if (log.type === 'wipe') {
                graphLogs[node_id] = [];
            }
            
            graphLogs[node_id].push(log);
        }
    }
    
    // Notify listeners
    if (logUpdateListeners[graph_id]) {
        for (const nodeId in logUpdateListeners[graph_id]) {
            // Check if there are logs for this node
            const nodeLogs = graphLogs[nodeId];
            if (nodeLogs) {
                for (const listener of logUpdateListeners[graph_id][nodeId]) {
                    listener(nodeLogs);
                }
            }
        }
    }
}

// Function to clear logs when Clear Outputs is clicked
export function clearNodeLogs(graph_id: string, node_id?: string) {
    if (!logsStore[graph_id]) return;
    
    if (node_id) {
        // Clear logs for a specific node
        if (logsStore[graph_id][node_id]) {
            logsStore[graph_id][node_id] = [];
            
            // Notify listeners for this node
            if (logUpdateListeners[graph_id] && logUpdateListeners[graph_id][node_id]) {
                for (const listener of logUpdateListeners[graph_id][node_id]) {
                    listener([]);
                }
            }
        }
    } else {
        // Clear all logs for the graph
        logsStore[graph_id] = {};
        
        // Notify all listeners for all nodes in this graph
        if (logUpdateListeners[graph_id]) {
            for (const nodeId in logUpdateListeners[graph_id]) {
                for (const listener of logUpdateListeners[graph_id][nodeId]) {
                    listener([]);
                }
            }
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

/**
 * Hook to subscribe to logs for a specific node in a graph
 * @param graphId The graph ID to subscribe to logs for
 * @param nodeId The node ID to subscribe to logs for, or 'all' for all nodes
 * @returns Array of log entries
 */
export function useLogSubscription(graphId: string, nodeId: string): LogEntry[] {
    const [logs, setLogs] = useState<LogEntry[]>([]);

    useEffect(() => {
        if (!graphId) return;
        
        // Create structure for graph if it doesn't exist
        if (!logUpdateListeners[graphId]) {
            logUpdateListeners[graphId] = {};
        }
        
        // Create array for node if it doesn't exist
        if (!logUpdateListeners[graphId][nodeId]) {
            logUpdateListeners[graphId][nodeId] = [];
        }
        
        // Add our listener
        logUpdateListeners[graphId][nodeId].push(setLogs);
        
        // Initial setup of logs if they exist already
        if (logsStore[graphId]) {
            if (logsStore[graphId][nodeId]) {
                setLogs(logsStore[graphId][nodeId]);
            }
        }
        
        // Cleanup
        return () => {
            if (logUpdateListeners[graphId] && logUpdateListeners[graphId][nodeId]) {
                logUpdateListeners[graphId][nodeId] = logUpdateListeners[graphId][nodeId].filter(
                    listener => listener !== setLogs
                );
            }
        };
    }, [graphId, nodeId]);
    
    return logs;
}
