import React from "react";
import { useReactFlow, Handle, Position } from "reactflow";

export function ExampleNode({ id }) {
    const { getNode } = useReactFlow();
    const node = getNode(id);

    return (
        <div>
            <h1>Node ID: {id}</h1>
            <pre>{JSON.stringify(node.data, null, 2)}</pre>
            <Handle
                type="source"
                position={Position.Right}
                id="resource" // id must be resource
                style={{ background: "#555", position: "absolute", right: 2 }}
                />
        </div>
    );
}
