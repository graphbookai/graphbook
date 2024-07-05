import type { Node, Edge } from 'reactflow';
/**
 * Handles the properties of each node for helpful information
 */
class Properties {
    protected properties: { [key: string]: any } = {};

    constructor() {
        this.properties = {};
    }

    public setProperty(nodeId: string, value: any) {
        this.properties[nodeId] = value;
    }

    public getProperty(nodeId: string) {
        return this.properties[nodeId];
    }
}

export const properties = new Properties();

class HandleProperties extends Properties {
    constructor() {
        super();
    }

    public setInputHandle(nodeId: string, handleId: string, handleType: string) {
        this.properties[nodeId] = {
            ...this.properties[nodeId],
            inputs: {
                ...this.properties[nodeId]?.inputs,
                [handleId]: {
                    type: handleType
                }
            }
        };
    }

    public setOutputHandle(nodeId: string, handleId: string, handleType: string) {
        this.properties[nodeId] = {
            ...this.properties[nodeId],
            outputs: {
                ...this.properties[nodeId]?.outputs,
                [handleId]: {
                    type: handleType
                }
            }
        };
    }

    public getInputHandle(nodeId: string, handleId: string) {
        return this.properties[nodeId]?.inputs[handleId];
    }

    public getOutputHandle(nodeId: string, handleId: string) {
        return this.properties[nodeId]?.outputs[handleId];
    }

    public setSubflowHandles(nodeId: string, subflow: { nodes: Node[]; edges: Edge[] }) {
        const setSubflow = (id: string, subflow: { nodes: Node[]; edges: Edge[] }) => {
            let inputCount = 0;
            let outputCount = 0;
    
            for (const node of subflow.nodes) {
                if (node.type === 'export') {
                    if (node.data?.exportType === 'input') {
                        this.setInputHandle(id, String(inputCount), node.data.isResource ? 'resource' : 'step');
                        inputCount++;
                    } else {
                        this.setOutputHandle(id, String(outputCount), node.data.isResource ? 'resource' : 'step');
                        outputCount++;
                    }
                } else if (node.type === 'subflow') {
                    setSubflow(nodeId+'/'+node.id, properties.getProperty(node.id)?.subflow);
                }
            }
        };

        setSubflow(nodeId, subflow);
    }
}

export const handleProperties = new HandleProperties();
