import { useState, useEffect } from 'react';
import { DAG, DAGNode } from '../graph';


let globalDAG: DAG = new DAG('');
let dagUsers: Function[] = [];
let nodesUsers: Function[] = [];

function onNodesChange() {
    nodesUsers.forEach((setter) => setter(globalDAG.getNodes()));
}

export function setDAG(dag: DAG) {
    globalDAG = dag;
    dagUsers.forEach((setter) => setter(globalDAG));
    dag.addNodesChangedCallback(onNodesChange);
}

export function useDAG(): DAG {
    const [_, setDAG] = useState(globalDAG);

    useEffect(() => {
        dagUsers.push(setDAG);

        return () => {
            dagUsers = dagUsers.filter((setter) => setter !== setDAG);
        }
    }, []);

    return globalDAG;
}

export function useNodes(): DAGNode[] {
    const [_, setNodes] = useState<DAGNode[]>([]);

    useEffect(() => {
        nodesUsers.push(setNodes);

        return () => {
            nodesUsers = nodesUsers.filter((setter) => setter !== setNodes);
        }
    }, []);

    return globalDAG.getNodes();
}
