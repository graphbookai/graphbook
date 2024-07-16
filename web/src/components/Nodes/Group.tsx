import React, { useCallback, useEffect, useState, useMemo } from 'react';
import { Flex, Card, Typography, theme, Badge } from 'antd';
import { NodeResizer, Handle, Position, useEdges, useNodes, useUpdateNodeInternals } from 'reactflow';
import type { Edge, Node } from 'reactflow';
import { useFilename } from '../../hooks/Filename';
import { useAPIMessage, useAPINodeMessage } from '../../hooks/API';
const { Text } = Typography;

const handleStyle = {
    borderRadius: '50%',
    top: '0%',
    right: 0,
    left: 0,
    transform: 'translate(0,0)',
};
const innerHandleStyle = {
    ...handleStyle,
    backgroundColor: '#fff',
    border: '2px dashed #4f4f4f',
}
const inHandleStyle = {
    ...handleStyle,
    marginRight: '2px',
};
const inInnerHandleStyle = {
    ...innerHandleStyle,
    marginLeft: '2px',
};
const outHandleStyle = {
    ...handleStyle,
    marginLeft: '2px'
};
const outInnerHandleStyle = {
    ...innerHandleStyle,
    marginRight: '2px',
};

export function Group({ id, data }) {
    const { label } = data;

    if (data.isCollapsed) {
        return <CollapsedGroup id={id} data={data} />;
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

function CollapsedGroup({ id, data }) {
    const { label } = data;

    return (
        <Card className='workflow-node group collapsed'>
            <Flex className='title' justify='space-between' style={{ margin: '0 2px' }}>
                <Text>{label}</Text>
            </Flex>
            <GroupPins id={id} data={data} />
        </Card>
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

    useEffect(() => {
        updateNodeInternals(id);
    }, [id, data.isCollapsed]);

    const updateRecordCount = useCallback((node, values) => {
        setRecordCount(prev => ({
            ...prev,
            [node]: values
        }));
    }, []);

    const c = data.isCollapsed;
    const handleContainerStyle = c ? {} : {
        backgroundColor: token.colorBgBase,
        borderRadius: '10%',
        padding: '2px 5px',
        margin: '1px 0'
    };

    const badgeIndicatorStyle = useMemo(() => ({
        fontSize: 8,
        padding: '0 1px',
        borderRadius: '25%',
        marginRight: 2,
        backgroundColor: token.colorBgBase,
        border: `1px solid ${token.colorPrimaryBorder}`,
        color: token.colorPrimaryText,
    }), [token]);

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

    useAPIMessage('stats', (msg: any) => {
        Object.entries<{queue_size: any}>(msg).forEach(([node, values]) => {
            if (subscribedNodes.has(node)) {
                console.log('updating record count', node, values);
                updateRecordCount(node, values.queue_size);
            }
        });
    });

    console.log('stepOutputs', stepOutputs);
    console.log('recordCounts', recordCount);

    return (
        <Flex vertical={true} className="handles">
            <div className="inputs">
                {
                    inputs
                        .sort(sortPinFn)
                        .map((input, i) => {
                            return (
                                <div key={i} className="input" style={handleContainerStyle}>
                                    <Handle style={inHandleStyle} type="target" position={Position.Left} id={String(input.id)} className={input.type === 'resource' ? 'parameter' : ''} />
                                    <Text style={{ alignSelf: 'left' }} className="label">{input.name}</Text>
                                    {!c && <Handle style={inInnerHandleStyle} type="source" position={Position.Right} id={`${input.id}_inner`} />}
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
                                    {!c && <Handle style={outInnerHandleStyle} type="target" position={Position.Left} id={`${output.id}_inner`} />}
                                    {c && <Badge size="small" styles={{indicator: badgeIndicatorStyle}} count={count} overflowCount={Infinity} />}
                                    <Text className="label">{output.name}</Text>
                                    <Handle style={outHandleStyle} type="source" position={Position.Right} id={String(output.id)} className={output.type === 'resource' ? 'parameter' : ''} />
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
