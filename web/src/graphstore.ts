import type { Node, Edge } from 'reactflow';
import type { ServerAPI } from './api';

/**
 * Note:
 * We should only put/update the graph on the below specified events:
 * - When a node is added -> onNodesChange ("type": "reset" nodes length is greater than previous nodes length)
 * - When a node is removed -> onNodesChange ("type": "remove")
 * - When a node's data is updated -> onNodesChange ("type": "reset", "data": { ... } (has to be different than previous data))
 * - When a node finishes resizing -> onNodesChange ("type": "dimensions", "resizing": false)
 * - When a node finishes moving -> onNodeDragStop
 * - When an edge is added -> onConnect
 * - When an edge is removed -> onEdgesChange ("type": "remove")
 */


// Tracks important state changes by keeping a copy of nodes and edges and receives updates to nodes and edges from Flow component
type GraphState = {
    nodes: Node[],
    edges: Edge[]
};

export class GraphStore {
    protected graphState: GraphState;
    protected filename: string;
    protected API: ServerAPI;

    constructor(filename: string, API: ServerAPI, nodes: Node[], edges: Edge[]) {
        this.filename = filename;
        this.API = API;
        this.graphState = { nodes, edges };
    }

    public update(nodes: Node[], edges: Edge[]) {
        if (this.isChanged(this.graphState, { nodes, edges })) {
            this.graphState = { nodes, edges };
            this.putGraph(nodes, edges);
        }
    }

    public updateNodePositions(nodes: Node[]) {
        let didUpdate = false;
        nodes.forEach(node => {
            const index = this.graphState.nodes.findIndex(n => n.id === node.id);
            if (index !== -1 && this.graphState.nodes[index].position !== node.position) {
                this.graphState.nodes[index].position = node.position;
                didUpdate = true;
            }
        });
        if (didUpdate) {
            this.putGraph(this.graphState.nodes, this.graphState.edges);
        }
    }

    protected putGraph(nodes, edges) {
        const storedNodes = nodes.map(node => {
            const storedNode = { ...node, data: { ...node.data } };
            delete storedNode.data.properties;
            delete storedNode.data.key;
            delete storedNode.selected;
            delete storedNode.dragging;
            delete storedNode.positionAbsolute;
            delete storedNode.width;
            delete storedNode.height;
            return storedNode;
        });
        const storedEdges = edges.map(edge => {
            const storedEdge = { ...edge, data: { ...edge.data } };
            delete storedEdge.data.properties;
            return storedEdge;
        });
        this.API.putGraph(this.filename, storedNodes, storedEdges);
    }

    private isChanged(prev: GraphState, next: GraphState) {
        // If node is added/removed
        if (prev.nodes.length !== next.nodes.length) {
            return true;
        }

        // If edge is added/removed
        if (prev.edges.length !== next.edges.length) {
            return true;
        }

        for (let i = 0; i < prev.nodes.length; i++) {
            // If node's data is updated
            const prevData = JSON.stringify({ ...prev.nodes[i].data, properties: undefined });
            const nextData = JSON.stringify({ ...next.nodes[i].data, properties: undefined });
            if (prevData !== nextData) {
                return true;
            }

            // If node is resized
            if (prev.nodes[i].type === 'group') {
                if (prev.nodes[i].width !== next.nodes[i].width || prev.nodes[i].height !== next.nodes[i].height) {
                    return true;
                }
            }
        }

        return false;
    }
}

export class PyGraphStore extends GraphStore {
    constructor(filename: string, API: ServerAPI, nodes: Node[], edges: Edge[]) {
        super(filename, API, nodes, edges);
    }

    protected putGraph(nodes, edges) {
        const storedNodes = nodes.map(node => {
            const storedNode = { ...node, data: { ...node.data } };
            delete storedNode.data.properties;
            delete storedNode.data.key;
            delete storedNode.selected;
            delete storedNode.dragging;
            delete storedNode.positionAbsolute;
            delete storedNode.width;
            delete storedNode.height;
            return storedNode;
        });
        const storedEdges = edges.map(edge => {
            const storedEdge = { ...edge, data: { ...edge.data } };
            delete storedEdge.data.properties;
            return storedEdge;
        });
        console.log("Put graph", storedNodes, storedEdges);
        this.API.putGraphV2(this.filename, storedNodes, storedEdges);
    }
}