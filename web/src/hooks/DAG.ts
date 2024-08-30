import { useState, useEffect } from 'react';
import { DAG } from '../graph';
import type { Node, Edge } from 'reactflow';

let globalDAG: DAG = new DAG();
let localSetters: Function[] = [];
export function updateDAG(nodes: Node[], edges: Edge[]) {
    globalDAG.update(nodes, edges);

    for (const setter of localSetters) {
        setter(globalDAG);
    }
}

export function useDAG(): DAG {
    const [_, setDAG] = useState(globalDAG);

    useEffect(() => {
        localSetters.push(setDAG);

        return () => {
            localSetters = localSetters.filter((setter) => setter !== setDAG);
        }
    }, []);

    return globalDAG;
}
