import { useState, useEffect, useCallback } from "react";
import { API } from "../api";
import { getGlobalFilename } from "./Filename";

export type RunState = 'changing' | 'running' | 'stopped';
let globalRunState: RunState = 'stopped';
let globalRunningFile: string = '';
let localSetters: Function[] = [];
let globalListenerIsSet = false;

export function useRunState(): [RunState, () => void] {
    const [_, setRunState] = useState<RunState>(globalRunState);

    useEffect(() => {
        const callback = (event) => {
            const message = JSON.parse(event.data);
            if (message.type !== 'run_state') {
                return;
            }
            if (message.is_running) {
                globalRunState = 'running';
            } else {
                globalRunState = 'stopped';
            }
            for (const setter of localSetters) {
                setter(globalRunState);
            }
        };
        
        if (!globalListenerIsSet) {
            API.addWSMessageListener(callback);
            globalListenerIsSet = true;
        }

        return () => {
            if (localSetters.length === 0) {
                API.removeWSMessageListener(callback);
                globalListenerIsSet = false;
            }
        }
    }, []);

    useEffect(() => {
        localSetters.push(setRunState);
        return () => {
            localSetters = localSetters.filter((setter) => setter !== setRunState);
        };
    }, []);

    const runStateShouldChange = useCallback(() => {
        globalRunState = 'changing';
        globalRunningFile = getGlobalFilename();

        for (const setter of localSetters) {
            setter(globalRunState);
        }
    }, []);

    return [globalRunState, runStateShouldChange];
}

export function getGlobalRunningFile() {
    return globalRunningFile;
}
