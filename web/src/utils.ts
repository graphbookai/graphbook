import { Node } from "reactflow";
import { Graph } from "./graph";
import type { ServerAPI } from "./api";
import type { ReactFlowInstance } from "reactflow";
import type { Ref } from "react";

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

export const mediaUrl = (url: string) : string => {
    return `http://localhost:8006/${url}`; // TODO: change in settings
}

export const uniqueIdFrom = (obj: any): string => {
    if (typeof(obj.length) === 'number') {
        return String(Math.max(Math.max(...obj.map(({id}) => parseInt(id))), -1) + 1);
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

        let type = 'resource';
        let label = 'Text';
        let parameters = { val: { type: "string", value: data.value } };
        if (data.value.endsWith('.json')) {
            const res = await API.getFile(data.value);
            if (res?.content) {
                const jsonData = JSON.parse(res.content);
                if (jsonData?.type === 'workflow') {
                    type = 'subflow';
                    label = data.value.split('/').pop().slice(0, -5);
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
            data: {
                name: label,
                parameters
            }
        }
        console.log("Adding node", node);
        setNodes(Graph.addNode(node, nodes));
    }

}

/**
 * Types of handles:
 * - step
 * - resource
 */
export function getHandle(node: Node, handleId: string, isTarget: boolean) {
    if (node.type === 'step') {
        return getStepHandle(node, handleId, isTarget);
    } else if(node.type === 'resource'){
        return getResourceHandle(node, handleId, isTarget);
    } else if(node.type === 'group'){
        return getGroupHandle(node, handleId, isTarget);
    } else {
        return getExportHandle(node, handleId, isTarget);
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
    } else  {
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
    return { ...toReturn, ...node.data.exports.inputs[handleId], nodeType: 'group'};
}

export function getExportedOutputHandle(node: Node, handleId: string) {
    const toReturn = {};
    if (handleId.endsWith('_inner')) {
        handleId = handleId.slice(0, -6);
        toReturn['inner'] = true;
    }
    return { ...toReturn, ...node.data.exports.outputs[handleId], nodeType: 'group' };
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
