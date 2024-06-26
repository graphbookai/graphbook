import { Node } from "reactflow";

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
    } else {
        return getGroupHandle(node, handleId, isTarget);
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
