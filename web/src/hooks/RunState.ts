import { useState, useEffect, useCallback } from "react";
import { useAPIAnyGraphLastValue } from "./API";

export type RunState = 'changing' | 'running' | 'finished';
let globalRunState: RunState = 'finished';
let globalRunningFile: string = '';
let localSetters: Function[] = [];

const updateRunState = (graphs) => {
    if (!graphs) {
        return;
    }

    for (const state of Object.values<RunState>(graphs)) {
        globalRunState = state;
        break;
    }

    for (const setter of localSetters) {
        setter(globalRunState);
    }
};

export function useRunState(): [RunState, () => void] {
    const [_, setRunState] = useState<RunState>(globalRunState);

    useEffect(() => {
        localSetters.push(setRunState);
        return () => {
            localSetters = localSetters.filter((setter) => setter !== setRunState);
        };
    }, []);

    const runStates = useAPIAnyGraphLastValue("run_state");

    useEffect(() => {
        updateRunState(runStates);
    }, [runStates]);

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
