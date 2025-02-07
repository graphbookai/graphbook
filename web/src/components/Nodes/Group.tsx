import React, { useCallback, useEffect, useState, useMemo } from 'react';
import { Flex, Card, Typography, theme, Badge } from 'antd';
import { NodeResizer, Handle, Position, useEdges, useNodes, useUpdateNodeInternals } from 'reactflow';
import { useAPIMessageEffect } from '../../hooks/API';
import { recordCountBadgeStyle, inputHandleStyle, outputHandleStyle, nodeBorderStyle } from '../../styles';
import type { Edge, Node } from 'reactflow';
import { useFilename } from '../../hooks/Filename';
import { getGlobalRunningFile } from '../../hooks/RunState';
const { Text } = Typography;


const innerHandleStyle = {
    backgroundColor: '#fff',
    border: '2px dashed #4f4f4f'
};

export function Group({ id, data, selected }) {
    const { label } = data;

    if (data.isCollapsed) {
        return <CollapsedGroup id={id} data={data} selected={selected}/>;
    }

    return (
        <div className='workflow-node group'>
            <NodeResizer minWidth={150} minHeight={150} />
            <Flex className='title' justify='space-between' style={{ margin: '0 2px' }}>
                <Text>{label}</Text>
            </Flex>
            <GroupPins id={id} data={data} />
        </div>
    );
}

function CollapsedGroup({ id, data, selected }) {
    const { label } = data;
    const { token } = theme.useToken();

    const borderStyle = useMemo(() => nodeBorderStyle(token, false, selected, false), [token, selected]);

    return (
        <div style={borderStyle}>
            <Card className='workflow-node group collapsed'>
                <Flex className='title' justify='space-between' style={{ margin: '0 2px' }}>
                    <Text>{label}</Text>
                </Flex>
                <GroupPins id={id} data={data} />
            </Card>
        </div>
    );
}

const sortPinFn = (a, b) => {
    if (a.type === b.type) {
        return Number(a.id) - Number(b.id);
    }
    return a.type === 'step' ? -1 : 1;
}

function GroupPins({ id, data }) {
    const { inputs, outputs } = data.exports;
    const { token } = theme.useToken();
    const edges: Edge[] = useEdges();
    const nodes: Node[] = useNodes();
    const [recordCount, setRecordCount] = useState({});
    const updateNodeInternals = useUpdateNodeInternals();
    const filename = useFilename();

    useEffect(() => {
        updateNodeInternals(id);
    }, [id, data.isCollapsed]);

    const c = data.isCollapsed;
    const handleContainerStyle = c ? {} : {
        backgroundColor: token.colorBgBase,
        borderRadius: '5px',
        padding: '2px 2px',
        margin: '1px 0'
    };

    const badgeIndicatorStyle = useMemo(() => recordCountBadgeStyle(token), [token]);

    const [subscribedNodes, stepOutputs] = useMemo(() => {
        const subscribedNodes = new Set<string>();
        const stepOutputs = {};
        for (const output of outputs) {
            if (output.type === 'step') {
                stepOutputs[output.id] = [];
            }
        }
        const outputEdges = edges.filter((edge) => edge.target === id && edge.targetHandle?.endsWith('_inner'));
        for (const edge of outputEdges) {
            const sourceNodeId = edge.source;
            const sourceNode = nodes.find((node) => node.id === sourceNodeId);
            if (!sourceNode) {
                continue;
            }
            const outputId = edge.targetHandle?.split('_')[0] || '';

            if (sourceNode?.type === 'step') {
                subscribedNodes.add(sourceNodeId);
                stepOutputs[outputId] = [...(stepOutputs[outputId] || []), { node: sourceNodeId, pin: edge.sourceHandle || '' }];
            } else if (sourceNode?.type === 'subflow') {
                const outputs = sourceNode.data.properties.stepOutputs[edge.sourceHandle || ''];
                for (const output of outputs) {
                    subscribedNodes.add(output.node);
                    stepOutputs[outputId] = [...(stepOutputs[outputId] || []), { node: output.node, pin: output.pin }];
                }
            }
        }
        return [subscribedNodes, stepOutputs];

    }, [outputs, edges, nodes, id]);

    const updateStats = useCallback((msg: any) => {
        Object.entries<{queue_size: any}>(msg).forEach(([node, values]) => {
            if (filename === getGlobalRunningFile() && subscribedNodes.has(node)) {
                setRecordCount(prev => ({
                    ...prev,
                    [node]: values.queue_size
                }));
            }
        });
    }, [filename, subscribedNodes, setRecordCount]);

    useAPIMessageEffect('stats', updateStats);

    const innerInputHandleStyle = useMemo(() => ({
        ...outputHandleStyle(),
        ...innerHandleStyle,
    }), []);

    
    const innerOutputHandleStyle = useMemo(() => ({
        ...inputHandleStyle(),
        ...innerHandleStyle,
    }), []);

    return (
        <Flex vertical={true} className="handles">
            <div className="inputs">
                {
                    inputs
                        .sort(sortPinFn)
                        .map((input, i) => {
                            return (
                                <div key={i} className="input" style={handleContainerStyle}>
                                    <Handle style={inputHandleStyle()} type="target" position={Position.Left} id={String(input.id)} className={input.type === 'resource' ? 'parameter' : ''} />
                                    <Text style={{ alignSelf: 'left' }} className="label">{input.name}</Text>
                                    {!c && <Handle style={innerInputHandleStyle} type="source" position={Position.Right} id={`${input.id}_inner`} />}
                                </div>
                            );
                        })
                }
            </div>
            <div className='outputs'>
                {
                    outputs
                        .sort(sortPinFn)
                        .map((output, i) => {
                            const count = stepOutputs[output.id]?.reduce((acc, { node, pin }) => {
                                return acc + (recordCount[node]?.[pin] || 0);
                            }, 0) || 0;
                            return (
                                <div key={i} className="output" style={handleContainerStyle}>
                                    {!c && <Handle style={innerOutputHandleStyle} type="target" position={Position.Left} id={`${output.id}_inner`} />}
                                    {c && <Badge size="small" styles={{indicator: badgeIndicatorStyle}} count={count} overflowCount={Infinity} />}
                                    <Text className="label">{output.name}</Text>
                                    <Handle style={outputHandleStyle()} type="source" position={Position.Right} id={String(output.id)} className={output.type === 'resource' ? 'parameter' : ''} />
                                </div>
                            );
                        })
                }
            </div>
        </Flex>
    );
}


export function groupIfPossible(changedNodes: Node[], allNodes: Node[]) {
    const groupNodes = allNodes.filter((node) => node.type === 'group');
    const changedNodesIds = changedNodes.map(({ id }) => id);
    return allNodes.map((node) => {
        if (node.type === 'group' || node.type === 'export' || !changedNodesIds.includes(node.id)) {
            return node;
        }

        const { position, width, height } = node;
        if (!width || !height) {
            return node;
        }

        for (const groupNode of groupNodes) {
            const gpos = groupNode.position;
            const w = groupNode.width;
            const h = groupNode.height;
            if (!w || !h) {
                continue;
            }
            const groupBounds = [gpos.x, gpos.y, gpos.x + w, gpos.y + h];

            if (node.parentId === groupNode.id) {
                if (!(position.x > 0 &&
                    position.y > 0 &&
                    position.x + width < w &&
                    position.y + height < h)
                ) {
                    node.parentId = '';
                    node.position = { x: position.x + gpos.x, y: position.y + gpos.y };
                }
            } else {
                if (position.x > groupBounds[0] &&
                    position.y > groupBounds[1] &&
                    position.x + width < groupBounds[2] &&
                    position.y + height < groupBounds[3]
                ) {
                    node.parentId = groupNode.id;
                    node.position = { x: position.x - gpos.x, y: position.y - gpos.y };
                }
            }
        }

        return node;
    });
}
