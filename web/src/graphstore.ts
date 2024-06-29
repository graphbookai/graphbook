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
    private graphState: GraphState;
    private filename: string;
    private API: ServerAPI;

    constructor(filename: string, API: ServerAPI, nodes: Node[], edges: Edge[]) {
        this.filename = filename;
        this.API = API;
        this.graphState = { nodes, edges };
    }

    public update(nodes: Node[], edges: Edge[]) {
        if (this.isChanged(this.graphState, { nodes, edges })) {
            this.graphState = { nodes, edges };
            this.API.putGraph(this.filename, nodes, edges);
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
            this.API.putGraph(this.filename, this.graphState.nodes, this.graphState.edges);
        }
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
            if (prev.nodes[i].data !== next.nodes[i].data) {
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
