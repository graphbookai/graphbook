import { useAPINodeMessage } from "./API";
import { useFilename } from "./Filename"
import { useEffect, useCallback } from "react";


let globalPrompts = {};

export function usePrompt(nodeId: string, callback: Function) {
    const filename = useFilename();

    useEffect(() => {
        return () => {
            delete globalPrompts[nodeId];
        };
    }, [nodeId]);

    const internalCallback = useCallback((data) => {
        if (globalPrompts[nodeId]) {
            return;
        }

        console.log(data);
        globalPrompts[nodeId] = data;
        callback(data);
    }, [nodeId]);

    useAPINodeMessage("prompt", nodeId, filename, internalCallback);
}
