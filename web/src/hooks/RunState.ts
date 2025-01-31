import { useState, useEffect, useCallback, useMemo } from "react";
import { useAPIEveryGraphLastValue, useAPIEveryGraphMessageEffect } from "./API";

export type RunState = 'changing' | 'running' | 'finished';
let globalRunState: RunState = 'finished';
let globalRunningFile: string = '';
let localSetters: Function[] = [];

export function useRunState(): [RunState, () => void] {
    const [_, setRunState] = useState<RunState>(globalRunState);

    useEffect(() => {
        localSetters.push(setRunState);
        return () => {
            localSetters = localSetters.filter((setter) => setter !== setRunState);
        };
    }, []);

    const runStates = useAPIEveryGraphLastValue("run_state");

    const runState = useMemo(() => {
        const isRunning = () => {
            for (const state of Object.values<RunState>(runStates)) {
                if (state === 'running') {
                    return true;
                }
            }
            return false;
        };

        if (isRunning()) {
            return 'running';
        } 
        
        return 'finished';
    }, [runStates]);

    const runStateShouldChange = useCallback(() => {
        globalRunState = 'changing';

        for (const setter of localSetters) {
            setter(globalRunState);
        }
    }, []);

    return [runState, runStateShouldChange];
}

export function getGlobalRunningFile() {
    return globalRunningFile;
}
