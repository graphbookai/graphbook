import { useState, useEffect, useCallback } from "react";
import { API } from "../api";

export type RunState = 'changing' | 'running' | 'stopped';
let globalRunState: RunState = 'stopped';
let localSetters: Function[] = [];
let globalListenerIsSet = false;

export function useRunState() {
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

        for (const setter of localSetters) {
            setter(globalRunState);
        }
    }, []);

    return [globalRunState, runStateShouldChange];
}
