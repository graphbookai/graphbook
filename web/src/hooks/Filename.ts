import { useState, useEffect } from 'react';

let globalFilename: string = '';
let localSetters: Function[] = [];
export function useFilename() {
    const [_, setFilename] = useState<string>(globalFilename);

    useEffect(() => {
        localSetters.push(setFilename);
        return () => {
            localSetters = localSetters.filter((setter) => setter !== setFilename);
        };
    }, []);

    return globalFilename;
}

export function setGlobalFilename(filename: string) {
    globalFilename = filename;
    for (const setter of localSetters) {
        setter(globalFilename);
    }
}

export function getGlobalFilename() {
    return globalFilename;
}
