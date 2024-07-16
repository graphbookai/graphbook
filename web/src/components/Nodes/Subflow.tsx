import React, { useMemo, useState, useCallback } from 'react';
import { Card, Typography, Flex, Button, Badge, theme } from 'antd';
import { CaretRightOutlined } from '@ant-design/icons';
import { useAPI, useAPIMessage } from '../../hooks/API';
import { useRunState } from '../../hooks/RunState';
import { useReactFlow, useOnSelectionChange, Position, Handle } from 'reactflow';
import { Graph } from '../../graph';
import { nodeBorderStyle, recordCountBadgeStyle } from '../../styles';
const { Text } = Typography;
const { useToken } = theme;

type Output = {
    node: string,
    pin: string,
};

const handleStyle = {
    borderRadius: '50%',
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
    const { getNode, getNodes, getEdges } = useReactFlow();
    const API = useAPI();
    const updateRecordCount = useCallback((node, values) => {
        setRecordCount({
            ...recordCount,
            [node]: values
        });
    }, [recordCount]);

    const subscribedNodes = useMemo(() => {
        const subscribedNodes = new Set<string>();
        for (const outputs of Object.values(data.properties.stepOutputs)) {
            for (const output of outputs as Output[]) {
                subscribedNodes.add(output.node);
            }
        }
        return subscribedNodes;
    }, [data.properties.stepOutputs]);

    useAPIMessage('stats', (msg: any) => {
        Object.entries<{queue_size: any}>(msg).forEach(([node, values]) => {
            if (subscribedNodes.has(node)) {
                updateRecordCount(node, values.queue_size);
            }
        });
    });

    const [inputs, outputs] = useMemo(() => {
        const inputs: any[] = [];
        const outputs: any[] = [];
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
                    outputs.push({
                        name: node.data.label,
                        isResource: node.data.isResource,
                        id: String(outputs.length)
                    });
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

    const borderStyle = useMemo(() => nodeBorderStyle(token, errored, selected, parentSelected), [token, errored, selected, parentSelected]);
    const badgeIndicatorStyle = useMemo(() => recordCountBadgeStyle(token), [token]);

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
                                .map((output, i) => {
                                    const count = data.properties.stepOutputs[output.id]?.reduce((acc, { node, pin }) => {
                                        return acc + (recordCount[node]?.[pin] || 0);
                                    }, 0) || 0;
                                    return (
                                        <div key={i} className="output">
                                            <Badge size="small" styles={{indicator: badgeIndicatorStyle}} count={count} overflowCount={Infinity} />
                                            <Text style={{alignSelf: 'right'}} className="label">{output.name}</Text>
                                            <Handle style={outHandleStyle} type="source" position={Position.Right} id={output.id} className={output.isResource ? 'parameter' : ''}/>
                                        </div>
                                    );
                                })
                        }
                    </div>
                </div>
            </Card>
        </div>
    );
}
