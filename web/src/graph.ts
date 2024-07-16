import { uniqueIdFrom } from './utils';
import { API } from './api';
import type { ServerAPI } from './api';
import type { Node, Edge } from 'reactflow';

const SERIALIZATION_ERROR = {
    INPUT_RESOLVE: 'Failed to resolve step input',
    PARAM_RESOLVE: 'Failed to resolve a parameter',
};

type SerializationError = {
    type: string,
    node: string,
    pin?: string,
};

type InputRef = {
    node: string,
    slot: string,
    isInner?: boolean,
};

type ParamRef = InputRef | number | string;

type SerializedStep = {
    name: string,
    inputs: InputRef[],
    parameters: { [key: string]: ParamRef },
};

type SerializedStepMap = {
    [id: string]: SerializedStep
};

type SerializedResource = {
    name: string,
    parameters: { [key: string]: ParamRef },
};

type SerializedResourceMap = {
    [id: string]: SerializedResource
};

export const checkForSerializationErrors = (G, resources): SerializationError[] => {
    const errors: SerializationError[] = [];
    Object.entries<SerializedStep>(G).forEach(([id, node]) => {
        node.inputs.forEach(input => {
            if (!G[input.node]) {
                errors.push({
                    type: SERIALIZATION_ERROR.INPUT_RESOLVE,
                    node: id,
                });
            }
        });
        Object.entries<ParamRef>(node.parameters).forEach(([key, param]) => {
            if (!(typeof param === 'string' || typeof param === 'number')) {
                if (!resources[param.node]) {
                    errors.push({
                        type: SERIALIZATION_ERROR.PARAM_RESOLVE,
                        node: id,
                        pin: key,
                    });
                }
            }
        });

    });
    Object.entries<SerializedResource>(resources).forEach(([id, node]) => {
        Object.entries<ParamRef>(node.parameters).forEach(([key, param]) => {
            if (!(typeof param === 'string' || typeof param === 'number')) {
                if (!resources[param.node]) {
                    errors.push({
                        type: SERIALIZATION_ERROR.PARAM_RESOLVE,
                        node: id,
                        pin: key,
                    });
                }
            }
        });
    });
    return errors;
};

export const Graph = {
    addNode(node, nodes) {
        const nextId = uniqueIdFrom(nodes);
        const newNode = { id: nextId.toString(), ...node };
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
    serializeForAPI: async (nodes, edges): Promise<[[SerializedStepMap, SerializedResourceMap], SerializationError[]]> => {
        const serialize = async (nodes, edges, parentId = "") => {
            const id = (id) => parentId + id;
            const G: { [id: string]: any } = {};
            const resources = {}
            const outputs = {};
            let exportCounts = {
                inputs: 0,
                outputs: 0
            }
            for (const node of nodes) {
                const common = {
                    type: node.type,
                    name: node.data.name
                };
                if (node.type === 'export') {
                    G[id(node.id)] = {
                        ...common,
                        parentId: parentId.slice(0, -1),
                    };
                    if (node.data.exportType === 'input') {
                        G[id(node.id)].handleId = String(exportCounts.inputs++);
                    } else {
                        G[id(node.id)].handleId = String(exportCounts.outputs++);
                    }
                } else if (node.type === 'subflow') {
                    const subflow = await API.getSubflowFromFile(node.data.filename);
                    if (!subflow) {
                        continue;
                    }
                    const [subflowG, subflowResources, subflowOutputs] = await serialize(subflow.nodes, subflow.edges, parentId + node.id + "/");
                    Object.assign(G, subflowG);
                    Object.assign(resources, subflowResources);
                    G[id(node.id)] = {
                        ...common,
                        inputs: {},
                        exports: {
                            inputs: {},
                            outputs: subflowOutputs
                        },
                    };
                } else if (node.type === 'group') {
                    G[id(node.id)] = {
                        ...common,
                        exports: {
                            inputs: {},
                            outputs: {}
                        },
                    };
                } else if (node.type === 'step' || node.type === 'resource') {
                    const parameters = {};
                    for (const [key, param] of Object.entries<{ node: string | null, value: string }>(node.data.parameters || {})) {
                        if (!param.node) {
                            parameters[key] = param.value;
                        }
                    }
                    if (node.type === 'step') {
                        G[id(node.id)] = {
                            ...common,
                            inputs: [],
                            parameters,
                        };
                    } else {
                        G[id(node.id)] = {
                            ...common,
                            parameters,
                        };
                    }
                } else {
                    console.warn('Unknown node type when serializing graph:', node.type);
                }
            };
            const setOutput = (node, slot, from = {}) => {
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
            const setSubflowOutput = (slot, from) => {
                const output = outputs[slot];
                if (output) {
                    output.push(from);
                } else {
                    outputs[slot] = [from];
                }
            };
            const setSubflowInput = (id, slot, from) => {
                const inputs = G[id].exports.inputs[slot];
                G[id].exports.inputs = {
                    ...G[id].exports.inputs,
                    [slot]: [...(inputs || []), from]
                };
            };
            edges.forEach((edge) => {
                let { source, target } = edge;
                source = id(source);
                target = id(target);
                const { sourceHandle, targetHandle } = edge;
                const sourceNode = G[source];
                const targetNode = G[target];
                if (!sourceNode || !targetNode) {
                    return;
                }

                const s = sourceHandle.endsWith('_inner') ? sourceHandle.slice(0, -6) : sourceHandle;
                const isInner = sourceHandle.endsWith('_inner');

                if (targetNode.type === 'export') {
                    setSubflowOutput(targetNode.handleId, { node: source, slot: s, isInner });
                } else {
                    if (targetNode.type === 'step') {
                        if (targetHandle === 'in') {
                            targetNode.inputs.push({ node: source, slot: s, isInner });
                        } else {
                            targetNode.parameters[targetHandle] = { node: source, slot: s, isInner };
                        }
                    } else if (targetNode.type === 'resource') {
                        targetNode.parameters[targetHandle] = { node: source, slot: s, isInner };
                    } else if (targetNode.type === 'group') {
                        if (targetHandle.endsWith('_inner')) { // case 3
                            setOutput(targetNode, targetHandle.slice(0, -6), { node: source, slot: s, isInner: true });
                        } else { // case 1
                            setInput(targetNode, targetHandle, { node: source, slot: s, isInner: false });
                        }
                    } else if (targetNode.type === 'subflow') {
                        setSubflowInput(target, targetHandle, { node: source, slot: s, isInner });
                    }
                }
            });

            return [G, resources, outputs];
        };
        const [G, resources] = await serialize(nodes, edges);

        const resolveInputs = (inputs) => {
            let newInputs: InputRef[] = [];
            Object.entries<InputRef>(inputs).forEach(([handleId, input]) => {
                let sourceNode = input.node;
                let sourceSlot = input.slot;
                if (G[sourceNode]) {
                    if ((G[sourceNode].type === 'group' && input.isInner) || G[sourceNode].type === 'export') {
                        if (G[sourceNode].type === 'export') {
                            sourceSlot = G[sourceNode].handleId;
                            sourceNode = G[sourceNode].parentId;
                            if (!sourceNode || !sourceSlot) {
                                return;
                            }
                        }
                        const groupInput = G[sourceNode].exports.inputs[sourceSlot];
                        if (groupInput) {
                            newInputs.push(...resolveInputs(groupInput));
                        }
                    } else if ((G[sourceNode].type === 'group' && !input.isInner) || G[sourceNode].type === 'subflow') {
                        const groupOutput = G[sourceNode].exports.outputs[sourceSlot];
                        if (groupOutput) {
                            newInputs.push(...resolveInputs(groupOutput));
                        }
                    } else if (G[sourceNode].type === 'step') {
                        newInputs.push({ node: sourceNode, slot: sourceSlot });
                    }
                }
            });
            return newInputs;
        };

        const resolveParameters = (parameters) => {
            let newParams = {};
            Object.entries<InputRef>(parameters).forEach(([handleId, input]) => {
                if (!input) {
                    return;
                }
                let sourceNode = input.node;
                let sourceSlot = input.slot;
                if (!sourceNode) {
                    return;
                }
                while (G[sourceNode] && G[sourceNode].type !== 'resource') {
                    let pin;
                    if ((G[sourceNode].type === 'group' && input.isInner) || G[sourceNode].type === 'export') {
                        if (G[sourceNode].type === 'export') {
                            sourceSlot = G[sourceNode].handleId;
                            sourceNode = G[sourceNode].parentId;
                            if (!sourceNode || !sourceSlot) {
                                break;
                            }
                        }
                        pin = G[sourceNode].exports.inputs[sourceSlot];
                    } else if ((G[sourceNode].type === 'group' && !input.isInner) || G[sourceNode].type === 'subflow') {
                        pin = G[sourceNode].exports.outputs[sourceSlot];
                    }
                    if (pin && pin[0]) {
                        sourceNode = pin[0].node;
                        sourceSlot = pin[0].slot;
                    } else {
                        sourceNode = '';
                        break;
                    }
                }
                if (G[sourceNode] && G[sourceNode].type === 'resource') {
                    newParams[handleId] = { node: sourceNode, slot: sourceSlot };
                }
            });
            return newParams;
        };
        Object.entries<any>(G).forEach(([id, node]) => {
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
        Object.entries<any>(G).forEach(([id, node]) => {
            if (node.type === 'resource') {
                resources[id] = node;
            }
            if (node.type !== 'step') {
                delete G[id];
            }
            delete node.type;
        });

        console.log(G);
        console.log(resources);
        const errors = checkForSerializationErrors(G, resources);
        return [[G, resources], errors];
    },
    serialize(nodes, edges) {
        return JSON.stringify({ nodes, edges });
    },
    deserialize(serialized) {
        return JSON.parse(serialized);
    },
    storeGraph(nodes, edges) {
        localStorage.setItem('graph', Graph.serialize(nodes, edges));
    },
    parseGraph: async (graph: any, API: ServerAPI) => {
        const resolveSubflowOutputs = (exportNode: Node, nodes: Node[], edges: Edge[], parent = "") => {
            const outputs: Array<{ node: string, pin: string }> = [];
            const sourceEdges = edges.filter((edge) => edge.target === exportNode.id);
            for (const edge of sourceEdges) {
                const exported = nodes.find((n) => n.id === edge.source);
                if (!exported) {
                    continue;
                }
                if (exported.type === 'step') {
                    outputs.push({ node: parent + "/" + exported.id, pin: edge.sourceHandle || '' });
                } else {
                    if (exported.type === 'group') {
                        const innerSourceHandle = `${edge.sourceHandle}_inner`;
                        for (const edge of edges) {
                            if (edge.targetHandle === innerSourceHandle) {
                                const innerExported = nodes.find((n) => n.id === edge.source);
                                if (!innerExported) {
                                    continue;
                                }
                                if (innerExported.type === 'step') {
                                    outputs.push({ node: parent + "/" + innerExported.id, pin: edge.sourceHandle || '' });
                                } else if (innerExported.type === 'subflow') {
                                    outputs.push(...innerExported.data.properties.stepOutputs[edge.sourceHandle || '']);
                                }
                            }
                        }
                    } else if (exported.type === 'subflow') {
                        outputs.push(...exported.data.properties.stepOutputs[edge.sourceHandle || '']);
                    }
                }
            }
            return outputs;
        };

        const parseNodes = async (nodes: Array<Node>) => {
            for (const node of nodes) {
                if (node.type === 'subflow') {
                    const file = await API.getFile(node.data.filename);
                    const subflowGraph = JSON.parse(file?.content);
                    if (subflowGraph?.type === 'workflow') {
                        node.data.properties = {
                            nodes: await parseNodes(subflowGraph.nodes),
                            edges: subflowGraph.edges,
                        };
                    }
                }
            }
            for (const node of nodes) {
                if (node.type === 'subflow') {
                    const stepOutputs = {};
                    let currentStepOutputId = 0;
                    for (const n of node.data.properties.nodes) {
                        if (n.type === 'export' && n.data.exportType === 'output' && !n.data.isResource) {
                            stepOutputs[currentStepOutputId++] = resolveSubflowOutputs(n, node.data.properties.nodes, node.data.properties.edges, node.id);
                        }
                    }
                    node.data.properties.stepOutputs = stepOutputs;
                }
            }
            return nodes;

        };

        const { nodes, edges } = graph;
        return [await parseNodes(nodes), edges]
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
        const q: string[] = [];
        const origin = connectingEdge.target;
        q.push(origin);
        while (q.length > 0) {
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