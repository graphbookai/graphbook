import { API } from './api';

export const Graph = {
    addNode(node, nodes) {
        const nextId = Math.max(Math.max(...nodes.map(({id}) => parseInt(id))), -1) + 1;
        const newNode = {id: nextId.toString(), visibility: 'visible', ...node};
        newNode.data.isCollapsed = false;
        API.putNode(newNode);
        
        return [...nodes, newNode];
    },
    editNodeData(nodeId, data, nodes) {
        const node = nodes.find((node) => node.id === nodeId);
        node.data = {
            ...node.data,
            ...data
        };
        return nodes;
    },
    editParamData(nodeId, paramName, data, nodes) {
        const node = nodes.find((node) => node.id === nodeId);
        node.data = {
            ...node.data,
            parameters: {
                ...node.data.parameters,
                [paramName]: {
                    ...node.data.parameters[paramName],
                    ...data
                }
            }
        };
        return nodes;
    },
    serializeForAPI(nodes, edges) {
        const G = {};
        const resources = {}
        nodes.forEach((node) => {
            const common = {
                // position: node.position
            }
            if (node.type === 'step') {
                const params = {};
                for (const [key, param] of Object.entries(node.data.parameters)) {
                    if (!param.node) {
                        params[key] = param.value;
                    }
                }
                G[node.id] = {
                    ...common,
                    name: node.data.name,
                    // position: node.position,
                    inputs: {
                        in: []
                    },
                    parameters: params
                };
            } else if (node.type.toLowerCase().includes('resource')) {
                if (node.type === 'codeResource' || node.type === 'fileResource') {
                    const parameters = {"val": node.data.value};
                    resources[node.id] = {
                        ...common,
                        name: 'BaseResource',
                        parameters
                    }
                } else {
                    const params = {};
                    for (const [key, param] of Object.entries(node.data.parameters)) {
                        if (!param.node) {
                            params[key] = param.value;
                        }
                    }
                    resources[node.id] = {
                        ...common,
                        name: node.data.name,
                        parameters: params
                    }
                }
            } else {
                console.warn('Unknown node type when serializing graph:', node.type);
            }
        });
        edges.forEach((edge) => {
            const {source, target, sourceHandle, targetHandle} = edge;
            const node = G[target];
            if (targetHandle === 'in') {
                node.inputs.in.push({ node: source, slot: sourceHandle });
            } else {
                node.parameters[targetHandle] = { node: source, slot: sourceHandle };
            }
        });
        console.log(G);
        console.log(resources);
        return [G, resources];
    },
    serialize(nodes, edges) {
        return JSON.stringify({nodes, edges});
    },
    deserialize(serialized) {
        return JSON.parse(serialized);
    },
    storeGraph(nodes, edges) {
        localStorage.setItem('graph', Graph.serialize(nodes, edges));
    },
    loadGraph() {
        const graph = localStorage.getItem('graph');
        if (graph) {
            return Graph.deserialize(graph);
        } else {
            return {nodes: [], edges: []};
        }
    },
    wouldBeCyclic(nodes, edges, connectingEdge) {
        if (connectingEdge.sourceHandle.endsWith('_inner') || connectingEdge.targetHandle.endsWith('_inner')) {
            return false;
        }
        const adjList = {};
        const isGroup = {};
        for (const node of nodes) {
            adjList[node.id] = [];
            isGroup[node.id] = node.type === 'group';
        }
        for (const edge of edges) {
            if (isGroup[edge.source] && edge.sourceHandle.endsWith('_inner')) {
                continue;
            }
            if (isGroup[edge.target] && edge.targetHandle.endsWith('_inner')) {
                continue;
            }
            if (!adjList[edge.source].includes(edge.target)) {
                adjList[edge.source].push(edge.target);
            }
        }
        adjList[connectingEdge.source].push(connectingEdge.target);
        const q = [];
        const origin = connectingEdge.target;
        q.push(origin);
        while(q.length > 0) {
            const [nodeId] = q.splice(0, 1);
            for (const childId of adjList[nodeId]) {
                if (childId === origin) {
                    return true;
                }
                q.push(childId);
            }
        }

        return false;

    }
}