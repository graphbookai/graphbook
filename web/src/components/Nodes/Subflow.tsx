import React, { useMemo, useState, useCallback, useEffect } from 'react';
import { Card, Typography, Flex, Button, theme } from 'antd';
import { CaretRightOutlined } from '@ant-design/icons';
import { useAPI } from '../../hooks/API';
import { useRunState } from '../../hooks/RunState';
import { useReactFlow, useOnSelectionChange, Position, Handle } from 'reactflow';
import { Graph } from '../../graph';
import { handleProperties } from '../../properties';
import type { Node, Edge } from 'reactflow';
const { Text } = Typography;
const { useToken } = theme;

type SubflowGraph = {
    nodes: Node[],
    edges: Edge[],
}

const handleStyle = {
    borderRadius: '50%',
    position: 'relative',
    top: '0%',
    right: 0,
    left: 0,
    transform: 'translate(0,0)',
};
const inHandleStyle = {
    ...handleStyle,
    marginRight: '5px'
};
const parameterHandleStyle = {
    ...inHandleStyle,
    borderRadius: '50%',
};
const outHandleStyle = {
    ...handleStyle,
    marginLeft: '5px'
};

export function Subflow({ id, data, selected }) {
    const { name } = data;
    const { token } = useToken();
    const [errored, setErrored] = useState(false);
    const [parentSelected, setParentSelected] = useState(false);
    const [subflowGraph, setSubflowGraph] = useState<SubflowGraph>({ nodes: [], edges: [] });
    const [runState, runStateShouldChange] = useRunState();
    const { getNode, getNodes, getEdges, setNodes } = useReactFlow();
    const API = useAPI();
    const { filename } = data;

    // useEffect(() => {
    //     if (!filename || !API) {
    //         return;
    //     }
    //     const fetchSubflow = async () => {
    //         const res = await API.getFile(filename);
    //         if (!res?.content) {
    //             setErrored(true);
    //             return;
    //         }
    //         const subflow = JSON.parse(res.content);
    //         if (!subflow?.nodes || !subflow?.edges) {
    //             setErrored(true);
    //             return;
    //         }
    //         setSubflowGraph(subflow);
    //     };
    //     fetchSubflow();
    // }, [filename, API]);

    useEffect(() => {
        const inputs: any[] = [];
        const outputs: any[] = [];
        for (const node of data.nodes) {
            if (node.type === 'export') {
                if (node.data?.exportType === 'input') {
                    inputs.push({
                        name: node.data.label,
                        isResource: node.data.isResource,
                        id: String(inputs.length)
                    });
                } else {
                    outputs.push({
                        name: node.data.label,
                        isResource: node.data.isResource,
                        id: String(outputs.length)
                    });
                }
            }
        }
        setNodes(Graph.editNodeData(id, { inputs, outputs }, getNodes()));
    }, [data]);

    const onSelectionChange = useCallback(({ nodes }) => {
        const parentId = getNode(id)?.parentId;
        if (!parentId) {
            return;
        }
        for (const n of nodes) {
            if (parentId === n.id && n.selected) {
                setParentSelected(true);
                return;
            }
        }
        setParentSelected(false);
    }, [id]);

    useOnSelectionChange({
        onChange: onSelectionChange
    });

    const borderStyle = useMemo(() => {
        const baseStyle = {
            padding: '1px',
            borderRadius: token.borderRadius,
            transform: 'translate(-2px, -2px)'
        };

        const selectedStyle = {
            ...baseStyle,
            border: `1px dashed ${token.colorInfoActive}`
        };

        const erroredStyle = {
            ...baseStyle,
            border: `1px solid ${token.colorError}`,
        };

        const parentSelectedStyle = {
            ...baseStyle,
            border: `1px dashed ${token.colorInfoBorder}`
        };

        if (errored) {
            return erroredStyle;
        }

        if (selected) {
            return selectedStyle;
        }

        if (parentSelected) {
            return parentSelectedStyle;
        }

    }, [token, errored, selected, parentSelected]);

    const run = useCallback(async () => {
        if (!API) {
            return;
        }
        const nodes = getNodes();
        const edges = getEdges();
        const [graph, resources] = await Graph.serializeForAPI(nodes, edges);
        API.run(graph, resources, id);
        runStateShouldChange();
    }, [API, id]);

    const { inputs, outputs } = data;

    return (
        <div style={borderStyle}>
            <Card className='workflow-node'>
                <Flex gap="small" justify='space-between' className='title'>
                    <div>{name}</div>
                    <Button shape="circle" icon={<CaretRightOutlined />} size={"small"} onClick={run} disabled={runState !== 'stopped'}/>
                </Flex>
                <div className="handles">
                    <div className="inputs">
                        {
                            (inputs || [])
                                .sort((a, b) => a.isResource ? -1 : 1)
                                .map((input, i) => (
                                <div key={i} className="input">
                                    <Handle style={inHandleStyle} type="target" position={Position.Left} id={input.id} className={input.isResource ? 'parameter' : ''}/>
                                    <Text style={{alignSelf: 'left'}} className="label">{input.name}</Text>
                                </div>
                            ))
                        }
                    </div>
                    <div className="outputs">
                        {
                            (outputs || [])
                                .sort((a, b) => a.isResource ? -1 : 1)
                                .map((output, i) => (
                                <div key={i} className="output">
                                    <Text style={{alignSelf: 'right'}} className="label">{output.name}</Text>
                                    <Handle style={outHandleStyle} type="source" position={Position.Right} id={output.id} className={output.isResource ? 'parameter' : ''}/>
                                </div>
                            ))
                        }
                    </div>
                </div>
            </Card>
        </div>
    );
}