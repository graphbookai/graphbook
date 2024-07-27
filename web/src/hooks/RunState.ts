import { useState, useEffect, useCallback } from "react";
import { useAPI } from "./API";

export type RunState = 'changing' | 'running' | 'stopped';
let globalRunState: RunState = 'stopped';
let globalRunningFile: string = '';
let localSetters: Function[] = [];
let initialized = false;

const updateRunState = (msg) => {
    if (msg) {
        if (msg.is_running) {
            globalRunState = 'running';
        } else {
            globalRunState = 'stopped';
        }
        globalRunningFile = msg.filename;
    } else {
        globalRunState = 'changing';
        globalRunningFile = '';
    }

    for (const setter of localSetters) {
        setter(globalRunState);
    }
};

export function useRunState(): [RunState, () => void] {
    const [_, setRunState] = useState<RunState>(globalRunState);
    const API = useAPI();

    useEffect(() => {
        localSetters.push(setRunState);
        return () => {
            localSetters = localSetters.filter((setter) => setter !== setRunState);
        };
    }, []);

    useEffect(() => {
        const globalEventListener = res => {
            const msg = JSON.parse(res.data);
            if (msg.type === 'run_state') {
                updateRunState(msg.data);
            }
        };

        (async () => {
            if (!initialized && API) {
                initialized = true;
                API.addWSMessageListener(globalEventListener)
                const runState = await API?.getRunState();
                updateRunState(runState);
            }

            return () => {
                if (localSetters.length === 0) {
                    API?.removeWSMessageListener(globalEventListener);
                    initialized = false;
                }
            };
        })();
    }, [API]);

    const runStateShouldChange = useCallback(() => {
        globalRunState = 'changing';

        for (const setter of localSetters) {
            setter(globalRunState);
        }
    }, []);

    return [globalRunState, runStateShouldChange];
}

export function getGlobalRunningFile() {
    return globalRunningFile;
}
