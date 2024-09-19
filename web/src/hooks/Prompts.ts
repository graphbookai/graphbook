import { useAPINodeMessage } from "./API";
import { useFilename } from "./Filename"
import { useEffect, useCallback, useState } from "react";


let globalPrompts = {};
let localSetters: Function[] = [];

type PromptData = {
    "idx": number,
    "note": object,
    "msg": string,
    "show_images": boolean,
    "def": any,
    "options": object,
    "type": string
};

type Prompt = {
    "note": object,
    "msg": string,
    "showImages": boolean,
    "def": any,
    "options": object,
    "type": string
};

export function usePrompt(nodeId: string): Prompt | null {
    const filename = useFilename();
    const [_, setPrompt] = useState<Prompt | null>(null);

    useEffect(() => {
        localSetters.push(setPrompt);
        return () => {
            localSetters = localSetters.filter((setter) => setter !== setPrompt);
            delete globalPrompts[nodeId];
        };
    }, [nodeId]);

    const onPrompt = useCallback((data: PromptData) => {
        if (globalPrompts[nodeId]) {
            if (globalPrompts[nodeId].idx === data.idx) {
                return;
            }
        }

        globalPrompts[nodeId] = data;
    }, [nodeId]);

    useAPINodeMessage("prompt", nodeId, filename, onPrompt);

    const promptData = globalPrompts[nodeId];
    if (!promptData) {
        return null;
    }

    return {
        note: promptData.note,
        msg: promptData.msg,
        showImages: promptData.show_images,
        def: promptData.def,
        options: promptData.options,
        type: promptData.type
    };
}
