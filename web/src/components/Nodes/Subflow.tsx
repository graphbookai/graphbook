import React, { useMemo, useState, useCallback, useEffect } from 'react';
import { Card, Typography, Flex, Button, theme } from 'antd';
import { CaretRightOutlined } from '@ant-design/icons';
import { useAPI, useAPINodeMessage } from '../../hooks/API';
import { useRunState } from '../../hooks/RunState';
import { useReactFlow, useOnSelectionChange, Position, Handle } from 'reactflow';
import { Graph } from '../../graph';
import { useFilename } from '../../hooks/Filename';
import type { Node, Edge } from 'reactflow';
const { Text } = Typography;
const { useToken } = theme;

type SubflowGraph = {
    nodes: Node[],
    edges: Edge[],
}

type Output = {
    node: string,
    pin: string,
};

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
    marginRight: '2px'
};
const outHandleStyle = {
    ...handleStyle,
    marginLeft: '2px'
};

export function Subflow({ id, data, selected }) {
    const { name } = data;
    const { token } = useToken();
    const [errored, setErrored] = useState(false);
    const [parentSelected, setParentSelected] = useState(false);
    const [runState, runStateShouldChange] = useRunState();
    const [recordCount, setRecordCount] = useState({});
    const { getNode, getNodes, getEdges, setNodes } = useReactFlow();
    const API = useAPI();
    const filename = useFilename();
    const updateRecordCount = useCallback((node, values) => {
        setRecordCount({
            ...recordCount,
            [node]: values
        });
    }, [recordCount]);

    useEffect(() => {
        const subscribedNodes = new Set<string>();
        for (const outputs of Object.values(data.properties.stepOutputs)) {
            for (const output of outputs as Output[]) {
                subscribedNodes.add(output.node);
            }
        }
        for (const node of subscribedNodes) {
            useAPINodeMessage('stats', node, filename, (msg) => {
                updateRecordCount(node, msg.queue_size);
            });
        }
    }, [data.properties.stepOutputs, filename]);

    // for (let [pin, outputs] of Object.entries(data.properties.stepOutputs)) {
    //     outputs = outputs as Array<Output>;

    //     for (const output of outputs) {
    //         useAPINodeMessage('stats', output.node, filename, (msg) => {
    //             // setRecordCount(msg.queue_size);
    //             updateRecordCount(pin, )
    //         });
    //     }

    // }

    console.log('subflow step outputs', data.properties.stepOutputs);

    const [inputs, outputs] = useMemo(() => {
        const inputs: any[] = [];
        const outputs: any[] = [];
        let currStepOutput = 0;
        if (!data.properties) {
            return [inputs, outputs];
        }

        for (const node of data.properties.nodes) {
            if (node.type === 'export') {
                if (node.data?.exportType === 'input') {
                    inputs.push({
                        name: node.data.label,
                        isResource: node.data.isResource,
                        id: String(inputs.length)
                    });
                } else {
                    let numRecords = 0;
                    for (const output of data.properties.stepOutputs[currStepOutput]) {
                        numRecords += recordCount[output.node][output.pin] || 0;
                    }
                    outputs.push({
                        name: node.data.label,
                        isResource: node.data.isResource,
                        id: String(outputs.length),
                        numRecords
                    });
                    currStepOutput++;
                }
            }
        }
        return [inputs, outputs];
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
