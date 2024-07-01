import { uniqueIdFrom } from './utils';

export const Graph = {
    addNode(node, nodes) {
        const nextId = uniqueIdFrom(nodes);
        const newNode = {id: nextId.toString(), ...node};
        newNode.data.isCollapsed = false;
        
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
            if (node.type === 'export') {
                return;
            }
            const common = {
                parameters: {},
                type: node.type
            };
            if (node.data.parameters) {
                for (const [key, param] of Object.entries(node.data.parameters)) {
                    if (!param.node) {
                        common.parameters[key] = param.value;
                    }
                }
            }
            if (node.type === 'step' || node.type === 'group') {
                G[node.id] = {
                    ...common,
                    name: node.data.name,
                    inputs: {},
                    exports: {
                        inputs: {},
                        outputs: {}
                    },
                };
            } else if (node.type === 'resource') {
                resources[node.id] = {
                    ...common,
                    name: node.data.name,
                };
                G[node.id] = resources[node.id];
            } else {
                console.warn('Unknown node type when serializing graph:', node.type);
            }
        });
        const setOutput = (node, slot, from={}) => {
            const output = node.exports.outputs[slot];
            if (output) {
                output.push(from);
            } else {
                node.exports.outputs[slot] = [from];
            }
        };
        const setInput = (node, slot, from) => {
            const input = node.exports.inputs[slot];
            if (input) {
                input.push(from);
            } else {
                node.exports.inputs[slot] = [from];
            }
        };
        edges.forEach((edge) => {
            const {source, target, sourceHandle, targetHandle} = edge;
            const sourceNode = G[source];
            const targetNode = G[target];

            if (targetNode.type === 'group') {
                if (targetHandle.endsWith('_inner')) { // case 3
                    setOutput(targetNode, targetHandle.slice(0, -6), { node: source, slot: sourceHandle });
                } else { // case 1
                    setInput(targetNode, targetHandle, { node: source, slot: sourceHandle });
                }
            }

            if (sourceNode.type === 'group') {
                if (sourceHandle.endsWith('_inner')) { // case 2
                    if (targetNode.type === 'step') {
                        if (targetHandle === 'in') {
                            targetNode.inputs[targetHandle] = { node: source, slot: sourceHandle.slice(0, -6), isInner: true };
                        } else {
                            targetNode.parameters[targetHandle] = { node: source, slot: sourceHandle.slice(0, -6), isInner: true };
                        }
                    }
                } else { // case 4
                    if (targetNode.type === 'step') {
                        if (targetHandle === 'in') {
                            targetNode.inputs[targetHandle] = { node: source, slot: sourceHandle, isInner: false };
                        } else {
                            targetNode.parameters[targetHandle] = { node: source, slot: sourceHandle, isInner: false };
                        }
                    }
                }
            } else if (sourceNode.type === 'step') {
                if (targetNode.type === 'step') {
                    if (targetHandle === 'in') {
                        targetNode.inputs[targetHandle] = { node: source, slot: sourceHandle };
                    }
                }
            } else if (sourceNode.type === 'resource') {
                if (targetNode.type === 'step') {
                    targetNode.parameters[targetHandle] = { node: source, slot: sourceHandle };
                }
            }
        });


        const resolveInputs = (inputs) => {
            let newInputs = [];
            Object.entries(inputs).forEach(([handleId, input]) => {
                let sourceNode = input.node;
                let sourceSlot = input.slot;
                if (G[sourceNode] && G[sourceNode].type === 'group') { // must be case 2 or 4 if groups cant be cascaded
                    if (input.isInner) { // case 2
                        const groupInput = G[sourceNode].exports.inputs[sourceSlot];
                        if (groupInput) {
                            newInputs.push(...resolveInputs(groupInput));
                        }
                    } else { // case 4
                        const groupOutput = G[sourceNode].exports.outputs[sourceSlot];
                        if (groupOutput && groupOutput) {
                            newInputs.push(...resolveInputs(groupOutput));
                        }
                    }
                }
                if (G[sourceNode] && G[sourceNode].type === 'step') {
                    newInputs.push({ node: sourceNode, slot: sourceSlot });
                }
            });
            return newInputs;
        };

        const resolveParameters = (parameters) => {
            let newParams = {};
            Object.entries(parameters).forEach(([handleId, input]) => {
                let sourceNode = input.node;
                let sourceSlot = input.slot;
                if (!sourceNode) {
                    return;
                }
                while (G[sourceNode] && G[sourceNode].type === 'group') { // must be case 2 or 4 if groups cant be cascaded
                    let pin;
                    if (input.isInner) { // case 2
                        pin = G[sourceNode].exports.inputs[sourceSlot];
                    } else { // case 4
                        pin = G[sourceNode].exports.outputs[sourceSlot];
                    }
                    if (pin && pin[0]) {
                        sourceNode = pin[0].node;
                        sourceSlot = pin[0].slot;
                    } else {
                        sourceNode = null;
                        break;
                    }
                }
                if (G[sourceNode] && G[sourceNode].type === 'resource') {
                    newParams[handleId] = { node: sourceNode, slot: sourceSlot };
                }
            });
            return newParams;
        };
        Object.entries(G).forEach(([id, node]) => {
            if (node.type !== 'step') {
                return;
            }
            const inputs = resolveInputs(node.inputs);
            const params = resolveParameters(node.parameters);
            node.inputs = inputs;
            node.parameters = {
                ...node.parameters,
                ...params
            };
            delete node.exports;
        });
        Object.entries(G).forEach(([id, node]) => {
            if (node.type !== 'step') {
                delete G[id];
            }
        });

        console.log(G);
        console.log(resources);
        return [G, resources];
    },
    serialize(nodes, edges) {
        console.log(JSON.stringify({nodes, edges}));
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