import { uniqueIdFrom, getHandle, Parameter } from './utils';
import { API } from './api';
import type { ServerAPI } from './api';
import type { Node, Edge, ReactFlowInstance, Connection } from 'reactflow';

export const SERIALIZATION_ERROR = {
    INPUT_RESOLVE: 'Failed to resolve step input',
    PARAM_RESOLVE: 'Failed to resolve a parameter',
};

export type SerializationError = {
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

export const resolveSubflowOutputs = (exportNode: Node, nodes: Node[], edges: Edge[], parent = "") => {
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
            if (!param) {
                errors.push({
                    type: SERIALIZATION_ERROR.PARAM_RESOLVE,
                    node: id,
                    pin: key,
                })
                return;
            }
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

    if (errors.length > 0) {
        console.log(errors);
    }
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
    parseGraph: async (graph: any, API: ServerAPI): Promise<[Node[], Edge[]]> => {
        const parseNodes = async (nodes: Node[]) => {
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

        const parseEdges = (nodes: Node[], edges: Edge[]) => {
            return edges.map((edge) => {
                const targetNode = nodes.find(n => n.id === edge.target)!;
                const sourceNode = nodes.find(n => n.id === edge.source)!;
                const targetHandle = getHandle(targetNode, edge.targetHandle!, true);
                const sourceHandle = getHandle(sourceNode, edge.sourceHandle!, false);
                return {
                    ...edge,
                    data: {
                        properties: {
                            targetHandle,
                            sourceHandle,
                            type: sourceHandle.type,
                        }

                    }
                };
            });
        };

        const { nodes, edges } = graph;
        return [await parseNodes(nodes), parseEdges(nodes, edges)];
    },
    wouldBeCyclic(nodes, edges, connectingEdge) {
        const adjList = {};
        const isGroup = {};
        let targetNode = null;
        for (const node of nodes) {
            if (node.id === connectingEdge.target) {
                targetNode = node;
            }
            if (node.type === 'group') {
                adjList[`${node.id}-i`] = [];
                adjList[`${node.id}-o`] = [];
                isGroup[node.id] = true;
            } else {
                adjList[node.id] = [];
            }
        }
        if (!targetNode) {
            return false;
        }
        const handle = getHandle(targetNode, connectingEdge.targetHandle, true);
        const edgeType = handle.type;

        for (const edge of edges) {
            if (edge.data.properties.type !== edgeType) {
                continue;
            }
            let s = edge.source;
            let t = edge.target;
            if (isGroup[s]) {
                if (edge.sourceHandle.endsWith('_inner')) {
                    s = `${edge.source}-i`;
                } else {
                    s = `${edge.source}-o`;
                }
            }
            if (isGroup[t]) {
                if (edge.targetHandle.endsWith('_inner')) {
                    t = `${edge.target}-o`;
                } else {
                    t = `${edge.target}-i`;
                }
            }
            adjList[s].push(t);
        }

        let s = connectingEdge.source;
        let t = connectingEdge.target;
        if (isGroup[connectingEdge.source]) {
            if (connectingEdge.sourceHandle.endsWith('_inner')) {
                s = `${connectingEdge.source}-i`;
            } else {
                s = `${connectingEdge.source}-o`;
            }
        }
        if (isGroup[connectingEdge.target]) {
            if (connectingEdge.targetHandle.endsWith('_inner')) {
                t = `${connectingEdge.target}-o`;
            } else {
                t = `${connectingEdge.target}-i`;
            }
        }

        adjList[s].push(t);
        const q: string[] = [];
        const origin = t;
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

// Modern DAG Model for abstraction of internal nodes and edges.
// Goal is to make this become completely used and replace other APIs in the future.
type DAGHandle = {
    type: "step" | "resource",
    connectedTo: DAGNode[],
    inner?: boolean,
};

class DAGNode {
    ref: Node;
    inputs: Map<string, DAGHandle>;
    outputs: Map<string, DAGHandle>;
    constructor(node: Node) {
        this.inputs = new Map();
        this.outputs = new Map();
        this.ref = node;
        this.setup();
    }

    private setup() {
        const { inputs, parameters, outputs } = this.ref.data;
        if (this.ref.type === 'step') {
            inputs.forEach(() => {
                this.inputs["in"] = { type: "step", connectedTo: [] };
            });
            Object.entries<Parameter>(parameters).forEach(([key, param]) => {
                this.inputs[key] = { type: "resource", connectedTo: [] };
            });
            outputs.forEach(key => {
                this.outputs[key] = { type: "step", connectedTo: [] };
            });
        } else if (this.ref.type === 'resource') {
            Object.entries<Parameter>(parameters).forEach(([key, param]) => {
                this.inputs[key] = { type: 'resource', connectedTo: [] };
            });
            this.outputs['resource'] = { type: 'resource', connectedTo: [] };
        } else if (this.ref.type === 'group') {
            const { inputs, outputs } = this.ref.data.exports;
            inputs.forEach(input => {
                this.inputs[input.id] = { type: input.type, inner: false, connectedTo: [] };
                this.outputs[`${input.id}_inner`] = { type: input.type, inner: true, connectedTo: [] };
            });
            outputs.forEach(output => {
                this.outputs[output.id] = { type: output.type, inner: false, connectedTo: [] };
                this.inputs[`${output.id}_inner`] = { type: output.type, inner: true, connectedTo: [] };
            });

        } else if (this.ref.type === 'export') {
            if (this.ref.data.exportType === 'input') {
                this.outputs["in"] = { type: this.ref.data.isResource ? 'resource' : 'step', connectedTo: [] };
            } else {
                this.inputs["out"] = { type: this.ref.data.isResource ? 'resource' : 'step', connectedTo: [] };
            }
        } else if (this.ref.type === 'subflow') {
            const { nodes } = this.ref.data.properties;
            if (nodes) {
                let numInputs = 0;
                let numOutputs = 0;

                for (const node of nodes) {
                    if (node.type === 'export') {
                        if (node.data?.exportType === 'input') {
                            this.inputs[String(numInputs++)] = { type: node.data.isResource ? 'resource' : 'step', connectedTo: [] };
                        } else {
                            this.outputs[String(numOutputs++)] = { type: node.data.isResource ? 'resource' : 'step', connectedTo: [] };
                        }
                    }
                }
            }
        }
    }

    public getOutput(id): DAGHandle {
        return this.outputs[id];
    }

    public getInput(id): DAGHandle {
        return this.inputs[id];
    }

    public refresh(): void {
        this.inputs.clear();
        this.outputs.clear();
        this.setup();
    }

    public connectInput(pin: string, node: DAGNode): void {
        this.inputs[pin].connectedTo.push(node);
    }

    public connectOutput(pin: string, node: DAGNode): void {
        this.outputs[pin].connectedTo.push(node);
    }
}

export class DAG {
    private nodes: Map<string, DAGNode>;

    constructor() {
        this.nodes = new Map();
    }

    public update(nodes, edges) {
        this.nodes.clear();
        nodes.forEach(node => {
            this.nodes.set(node.id, new DAGNode(node));
        });
        edges.forEach(edge => {
            const sourceNode = this.nodes.get(edge.source);
            const targetNode = this.nodes.get(edge.target);
            if (sourceNode && targetNode) {
                console.log("Connecting", sourceNode, targetNode);
                sourceNode.connectOutput(edge.sourceHandle, targetNode);
                targetNode.connectInput(edge.targetHandle, sourceNode);
            }
        });
        console.log("updated dag with nodes", this.nodes);
    }

    public isValidConnection(connection: Connection) {
        if (!connection.source || !connection.target || !connection.sourceHandle || !connection.targetHandle) {
            return false;
        }
        const srcNode = this.nodes.get(connection.source);
        const tgtNode = this.nodes.get(connection.target);
        if (!srcNode || !tgtNode) {
            return false;
        }

        const srcHandle = srcNode.getOutput(connection.sourceHandle);
        const tgtHandle = tgtNode.getInput(connection.targetHandle);
        // const srcHandle = getHandle(srcNode, connection.sourceHandle, false);
        // const tgtHandle = getHandle(tgtNode, connection.targetHandle, true);

        if (!srcHandle || !tgtHandle) {
            return false;
        }

        if (srcNode.ref.id === tgtNode.ref.id) {
            return false;
        }

        if (srcHandle.type !== tgtHandle.type) {
            return false;
        }

        console.log("A")
        if (srcNode.ref.type === 'group') {
            if (srcHandle.inner && tgtNode.ref.parentId !== srcNode.ref.id) {
                return false;
            }
            if (!srcHandle.inner && tgtNode.ref.parentId === srcNode.ref.id) {
                return false;
            }
        }

        console.log("B")
        if (tgtNode.ref.type === 'group') {
            if (tgtHandle.inner && srcNode.ref.parentId !== tgtNode.ref.id) {
                return false;
            }
            if (!tgtHandle.inner && srcNode.ref.parentId === tgtNode.ref.id) {
                return false;
            }
        }

        console.log("C")
        if (srcNode.ref.type === 'export' && tgtNode.ref.type === 'export') {
            return false;
        }

        // const edges = getEdges();
        // if (tgtHandle.type === 'resource') {
        //     for (const edge of edges) {
        //         if (edge.target === connection.target && edge.targetHandle === connection.targetHandle) {
        //             return false;
        //         }
        //     }
        // }

        // Only 1 connection to a target resource handle at a time
        console.log("D")
        if (tgtHandle.type === 'resource') {
            if (tgtHandle.connectedTo.length > 0) {
                return false;
            }
        }

        console.log("E")
        if (this.wouldBeCyclic(connection)) {
            // notificationCtrl.error({
            //     key: 'no-cycles',
            //     message: 'No Cycles',
            //     description: 'Graphbook only supports DAGs',
            //     duration: 1,
            // });
            return false;
        }
        console.log("F")

        return true;
    }

    private wouldBeCyclic(connection): boolean {
        const adjList = {};
        const sourceNode = this.nodes.get(connection.source);
        const targetNode = this.nodes.get(connection.target);
        if (!sourceNode || !targetNode) {
            return false;
        }

        const cycleType = targetNode.getInput(connection.targetHandle).type;
        const pushConnections = (nodeId: string, handle: DAGHandle) => {
            if (handle.type !== cycleType) {
                return;
            }
            for (const connectedTo of handle.connectedTo) {
                if (connectedTo.ref.type === 'group') {
                    if (handle.inner) {
                        adjList[nodeId].push(`${connectedTo.ref.id}-i`);
                    } else {
                        adjList[nodeId].push(`${connectedTo.ref.id}-o`);
                    }
                } else {
                    adjList[nodeId].push(connectedTo.ref.id);
                }
            }
        };

        for (const [id, node] of this.nodes) {
            if (node.ref.type === 'group') {
                adjList[`${id}-i`] = [];
                adjList[`${id}-o`] = [];
                for (const handle of Object.values(node.outputs)) {
                    if (handle.inner) {
                        pushConnections(`${id}-i`, handle);
                    } else {
                        pushConnections(`${id}-o`, handle);
                    }
                }
            } else {
                adjList[id] = [];
                for (const handle of Object.values(node.outputs)) {
                    pushConnections(id, handle);
                }
            }
        }

        let s = connection.source;
        let t = connection.target;
        if (sourceNode.ref.type === 'group') {
            if (connection.sourceHandle.endsWith('_inner')) {
                s = `${connection.source}-i`;
            } else {
                s = `${connection.source}-o`;
            }
        }
        if (targetNode.ref.type === 'group') {
            if (connection.targetHandle.endsWith('_inner')) {
                t = `${connection.target}-o`;
            } else {
                t = `${connection.target}-i`;
            }
        }

        adjList[s].push(t);
        const q: string[] = [];
        const origin = t;
        q.push(origin);
        while (q.length > 0) {
            const [nodeId] = q.splice(0, 1);
            console.log(nodeId, adjList[nodeId]);
            for (const childId of adjList[nodeId]) {
                console.log(childId);
                if (childId === origin) {
                    return true;
                }
                q.push(childId);
            }
        }

        return false;
    }

    // May not be needed
    // // Add a new node to the DAG
    // public addNode(node: Node): void {
    //     const dagNode = new DAGNode(node);
    //     this.nodes.set(node.id, dagNode);
    // }

    // // Remove a node from the DAG by id
    // public removeNode(nodeId: string): void {
    //     this.nodes.delete(nodeId);
    // }

    // // Add a new edge to the DAG
    // public addEdge(edge: Edge): void {
    //     this.flow.setEdges(edges => [...edges, edge]);
    // }

    // // Remove an edge from the DAG by id
    // public removeEdge(edgeId: string): void {
    //     this.flow.setEdges(edges => edges.filter(edge => edge.id !== edgeId));
    // }

    // // Get all nodes
    // public getNodes(): Node[] {
    //     return this.flow.getNodes();
    // }

    // // Get all edges
    // public getEdges(): Edge[] {
    //     return this.flow.getEdges();
    // }

    // // Find a node by id
    // public findNodeById(nodeId: string): Node | undefined {
    //     return this.flow.getNode(nodeId);
    // }

    // // Find edges connected to a node
    // public findEdgesByNodeId(nodeId: string): Edge[] {
    //     return this.flow.getEdges().filter(edge => edge.source === nodeId || edge.target === nodeId);
    // }
}
