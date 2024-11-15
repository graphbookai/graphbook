import { Graph, resolveSubflowOutputs } from "./graph";
import type { ServerAPI } from "./api";
import type { ReactFlowInstance } from "reactflow";
import type { Node } from "reactflow";

export const parseDictWidgetValue = (entries) => {
    const obj = {};
    for (const [type, key, val] of entries) {
        obj[key] = val;
    }
    return obj;
};

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

export type ImageRef = {
    type: string;
    value: string;
    shm_id?: string;
};
export const getMediaPath = (settings: any, item: ImageRef): string => {
    let query = '';
    if (item.shm_id) {
        query = `?shm_id=${item.shm_id}`;
    } else if (!item.value.startsWith('(')) {
        query = `?path=${item.value}`;
    } else {
        return '';
    }

    if (!settings.useExternalMediaServer) {
        let graphHost = settings.graphServerHost;
        if (!graphHost.startsWith('http')) {
            graphHost = 'http://' + graphHost;
        }
        return `${graphHost}/media${query}`;
    }

    let mediaHost = settings.mediaServerHost;
    if (!mediaHost.startsWith('http')) {
        mediaHost = 'http://' + query;
    }

    return mediaHost + query;
}

export const uniqueIdFrom = (obj: any): string => {
    if (typeof (obj.length) === 'number') {
        return String(Math.max(Math.max(...obj.map(({ id }) => parseInt(id))), -1) + 1);
    } else {
        return String(Math.max(...Object.keys(obj).map((key) => parseInt(key)), -1) + 1);
    }
}


export const bindDragData = (value: object, e: DragEvent) => {
    if (e) {
        e.dataTransfer?.setData('application/json', JSON.stringify(value));
    }
}

export const evalDragData = async (reactFlowInstance: ReactFlowInstance, API: ServerAPI, e: DragEvent) => {
    if (e?.dataTransfer) {
        const data = JSON.parse(e.dataTransfer.getData("application/json"));
        if (!data.node && !data.text && !data.subflow) {
            return;
        }

        const { setNodes, getNodes } = reactFlowInstance;
        const dropPosition = reactFlowInstance.screenToFlowPosition({ x: e.clientX, y: e.clientY });
        const nodes = getNodes();
        const id = uniqueIdFrom(nodes);

        if (data.node) {
            const node = {
                id,
                position: dropPosition,
                ...data.node
            };
            Object.values<any>(node.data.parameters).forEach((p) => {
                p.value = p.default;
            });
            setNodes(Graph.addNode(node, nodes));
        } else if (data.text) {
            const id = uniqueIdFrom(nodes);
            const node = {
                id,
                position: dropPosition,
                type: 'resource',
                data: {
                    name: 'Text',
                    label: 'Text',
                    parameters: { val: { type: "string", value: data.text } }
                }
            }
            setNodes(Graph.addNode(node, nodes));
        } else if (data.subflow) {
            const res = await API.getFile(data.subflow);
            if (res?.content) {
                const jsonData = JSON.parse(res.content);
                if (jsonData?.type === 'workflow') {
                    const name = data.subflow.split('/').pop().slice(0, -5);
                    const stepOutputs = {};
                    let currentStepOutputId = 0;
                    for (const n of jsonData.nodes) {
                        if (n.type === 'export' && n.data.exportType === 'output' && !n.data.isResource) {
                            stepOutputs[currentStepOutputId++] = resolveSubflowOutputs(n, jsonData.nodes, jsonData.edges, id);
                        }
                    }
                    const node = {
                        id,
                        position: dropPosition,
                        type: 'subflow',
                        data: {
                            name,
                            label: name,
                            filename: data.subflow,
                            properties: {
                                nodes: jsonData.nodes,
                                edges: jsonData.edges,
                                stepOutputs
                            }
                        }
                    }
                    setNodes(Graph.addNode(node, nodes));
                }
            }
        }
    }
};

export type LogEntry = {
    type: string,
    msg?: string
};

export const getMergedLogs = (prevLogs: Array<LogEntry>, newLogs: Array<LogEntry>) => {
    let wipeIndex = -1;
    for (let i = 0; i < newLogs.length; i++) {
        if (newLogs[i].type === 'wipe') {
            wipeIndex = i;
        }
    }

    if (wipeIndex > -1) {
        newLogs = newLogs.slice(wipeIndex + 1);
        return newLogs;
    }

    return [...prevLogs, ...newLogs];
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

export type Parameter = {
    type: string;
    value?: any;
    default?: any;
    description?: string;
    required?: boolean;
};
