import { Graph } from "./graph";
import type { ServerAPI } from "./api";
import type { ReactFlowInstance } from "reactflow";
import type { Node, Edge } from "reactflow";

export const keyRecursively = (obj: Array<any>, childrenKey: string = "children"): Array<any> => {
    let currKeyVal = 0;
    const keyRec = (obj: Array<any>) => {
        return obj.map((item) => {
            if (item[childrenKey]) {
                return {
                    ...item,
                    key: currKeyVal++,
                    [childrenKey]: keyRec(item[childrenKey])
                }
            }
            return {
                ...item,
                key: currKeyVal++
            };
        });
    }

    return keyRec(obj);
}

export const mediaUrl = (url: string): string => {
    return `http://localhost:8006/${url}`; // TODO: change in settings
}

export const uniqueIdFrom = (obj: any): string => {
    if (typeof (obj.length) === 'number') {
        return String(Math.max(Math.max(...obj.map(({ id }) => parseInt(id))), -1) + 1);
    } else {
        return String(Math.max(...Object.keys(obj).map((key) => parseInt(key)), -1) + 1);
    }
}


export const filesystemDragBegin = (value: string, e: DragEvent) => {
    if (e) {
        e.dataTransfer?.setData('application/json', JSON.stringify({ value }));
    }
}

export const filesystemDragEnd = async (reactFlowInstance: ReactFlowInstance, API: ServerAPI, e: DragEvent) => {
    if (e?.dataTransfer) {
        const data = JSON.parse(e.dataTransfer.getData("application/json"));
        if (!data.value) {
            return;
        }

        let nodeData: any = {
            name: 'Text',
            parameters: { val: { type: "string", value: data.value } }
        };
        let type = 'resource';
        if (data.value.endsWith('.json')) {
            const res = await API.getFile(data.value);
            if (res?.content) {
                const jsonData = JSON.parse(res.content);
                if (jsonData?.type === 'workflow') {
                    type = 'subflow';
                    const name = data.value.split('/').pop().slice(0, -5);
                    nodeData = {
                        name,
                        label: name,
                        filename: data.value,
                        properties: {
                            nodes: jsonData.nodes,
                            edges: jsonData.edges
                        }
                    }
                }
            }
        }
        const { setNodes, getNodes } = reactFlowInstance;
        const dropPosition = reactFlowInstance.screenToFlowPosition({ x: e.clientX, y: e.clientY });

        const nodes = getNodes();
        const node = {
            id: uniqueIdFrom(nodes),
            position: dropPosition,
            type,
            data: nodeData
        }
        setNodes(Graph.addNode(node, nodes));
    }
}

export const parseGraph = async (graph: any, API: ServerAPI) => {
    const resolveSubflowOutputs = (exportNode: Node, nodes: Node[], edges: Edge[], parent="") => {
        const outputs: Array<{node: string, pin: string}> = [];
        console.log(nodes);
        const sourceEdges = edges.filter((edge) => edge.target === exportNode.id);
        for (const edge of sourceEdges) {
            const exported = nodes.find((n) => n.id === edge.source);
            if (!exported) {
                continue;
            }
            if (exported.type === 'step') {
                outputs.push({ node: parent+"/"+exported.id, pin: edge.sourceHandle || '' });
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
                                outputs.push({ node: parent+"/"+innerExported.id, pin: edge.sourceHandle || '' });
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
                    console.log(node);
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
    return [ await parseNodes(nodes), edges]
};

/**
 * Types of handles:
 * - step
 * - resource
 */
export function getHandle(node: Node, handleId: string, isTarget: boolean) {
    if (node.type === 'step') {
        return getStepHandle(node, handleId, isTarget);
    } else if (node.type === 'resource') {
        return getResourceHandle(node, handleId, isTarget);
    } else if (node.type === 'group') {
        return getGroupHandle(node, handleId, isTarget);
    } else if (node.type === 'export') {
        return getExportHandle(node, handleId, isTarget);
    } else {
        return getSubflowHandle(node, handleId, isTarget);
    }
}

/**
 * Step nodes
 */
function getStepHandle(node: Node, handleId: string, isTarget: boolean) {
    if (isTarget) {
        if (handleId === 'in') {
            return { id: 'in', type: 'step', inner: false, nodeType: 'step' };
        }

        const parameters = node.data.parameters;
        if (parameters && parameters[handleId]) {
            return { id: handleId, type: 'resource', inner: false, nodeType: 'step' };
        }
    } else {
        const outputs = node.data.outputs;
        if (outputs && outputs.includes(handleId)) {
            return { id: handleId, type: 'step', inner: false, nodeType: 'step' };
        }
    }

    return null;
}

/**
 * Resource nodes
 */
function getResourceHandle(node: Node, handleId: string, isTarget: boolean) {
    if (isTarget) {
        const parameters = node.data.parameters;
        if (parameters && parameters[handleId]) {
            return { id: handleId, type: 'resource', inner: false, nodeType: 'resource' };
        }
    } else {
        if (handleId === 'resource') {
            return { id: handleId, type: 'resource', inner: false, nodeType: 'resource' };
        }
    }

    return null;
}

/**
 * Group nodes
 */
export function getGroupHandle(node: Node, handleId: string, isTarget: boolean) {
    if (isTarget) {
        if (isInternalHandle(handleId)) {
            return getExportedOutputHandle(node, handleId);
        } else {
            return getExportedInputHandle(node, handleId);
        }
    } else {
        if (isInternalHandle(handleId)) {
            return getExportedInputHandle(node, handleId);
        } else {
            return getExportedOutputHandle(node, handleId);
        }
    }
}


export function getExportedInputHandle(node: Node, handleId: string) {
    const toReturn = {};
    if (handleId.endsWith('_inner')) {
        handleId = handleId.slice(0, -6);
        toReturn['inner'] = true;
    }
    return { ...toReturn, ...node.data.exports.inputs.find(({ id }) => id === handleId), nodeType: 'group' };
}

export function getExportedOutputHandle(node: Node, handleId: string) {
    const toReturn = {};
    if (handleId.endsWith('_inner')) {
        handleId = handleId.slice(0, -6);
        toReturn['inner'] = true;
    }
    return { ...toReturn, ...node.data.exports.outputs.find(({ id }) => id === handleId), nodeType: 'group' };
}

export function isInternalHandle(handleId: string) {
    return handleId.endsWith('_inner');
}


/**
 * Export Handles
 */
export function getExportHandle(node: Node, handleId: string, isTarget: boolean) {
    const type = node.data.isResource ? 'resource' : 'step';
    return { id: handleId, type, inner: false, nodeType: 'export' };
}

/**
 * Export Handles
 */
export function getSubflowHandle(node: Node, handleId: string, isTarget: boolean) {
    const index = parseInt(handleId);
    if (isTarget) {
        const inputs = node.data.properties.nodes.filter((n) => n.type === 'export' && n.data.exportType === 'input');
        const input = inputs[index];
        const type = input.data.isResource ? 'resource' : 'step';
        return { id: handleId, type, inner: false, nodeType: 'subflow' };
    }

    const outputs = node.data.properties.nodes.filter((n) => n.type === 'export' && n.data.exportType === 'output');
    const output = outputs[index];
    const type = output.data.isResource ? 'resource' : 'step';
    return { id: handleId, type, inner: false, nodeType: 'subflow' };
}
