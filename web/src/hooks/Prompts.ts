import { useAPINodeMessageEffect } from "./API";
import { useFilename } from "./Filename"
import { useEffect, useCallback, useState } from "react";


let globalPrompts = {};
let localSetters: Function[] = [];

type PromptData = {
    "idx": number,
    "data": object,
    "msg": string,
    "show_images": boolean,
    "def": any,
    "options": object,
    "type": string
};

export type Prompt = {
    "data": object,
    "msg": string,
    "showImages": boolean,
    "def": any,
    "options": object,
    "type": string
};

const dataToPrompt = (data: PromptData): Prompt => ({
    data: data.data,
    msg: data.msg,
    showImages: data.show_images,
    def: data.def,
    options: data.options,
    type: data.type
});

export function usePrompt(nodeId: string, callback?: (p: Prompt) => void | null): Function {
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
        if (callback) {
            callback(dataToPrompt(data));
        }
    }, [nodeId]);

    const setSubmitted = useCallback(() => {
        if (!globalPrompts[nodeId]) {
            return;
        }
        globalPrompts[nodeId] = { ...globalPrompts[nodeId], "type": null };
    }, []);

    useAPINodeMessageEffect("prompt", nodeId, filename, onPrompt);

    return setSubmitted;
}
