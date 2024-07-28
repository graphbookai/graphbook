import React, { useMemo, useState, useCallback } from 'react';
import { Card, Typography, Badge, theme } from 'antd';
import { useAPI, useAPIMessage } from '../../hooks/API';
import { useRunState } from '../../hooks/RunState';
import { useReactFlow, useOnSelectionChange, Position, Handle } from 'reactflow';
import { Graph } from '../../graph';
import { nodeBorderStyle, recordCountBadgeStyle, inputHandleStyle, outputHandleStyle } from '../../styles';
import { useFilename } from '../../hooks/Filename';
import { getGlobalRunningFile } from '../../hooks/RunState';
import { useNotification } from '../../hooks/Notification';
import { SerializationErrorMessages } from '../Errors.tsx';
const { Text } = Typography;
const { useToken } = theme;

type Output = {
    node: string,
    pin: string,
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
    const filename = useFilename();
    const notification = useNotification();

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

    useAPIMessage('stats', updateStats);

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
        const [[graph, resources], errors] = await Graph.serializeForAPI(nodes, edges);
        if (errors.length > 0) {
            notification.error({
                key: 'invalid-graph',
                message: 'Invalid Graph',
                description: <SerializationErrorMessages errors={errors}/>,
                duration: 3,
            })
            return;
        }
        API.run(graph, resources, id, filename);
        runStateShouldChange();
    }, [API, id, notification, filename]);

    return (
        <div style={borderStyle}>
            <Card className='workflow-node'>
                <div className='title'>
                    {name}
                </div>
                <div className="handles">
                    <div className="inputs">
                        {
                            (inputs || [])
                                .sort((a, b) => a.isResource ? -1 : 1)
                                .map((input, i) => (
                                <div key={i} className="input">
                                    <Handle style={inputHandleStyle()} type="target" position={Position.Left} id={input.id} className={input.isResource ? 'parameter' : ''}/>
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
                                            <Handle style={outputHandleStyle()} type="source" position={Position.Right} id={output.id} className={output.isResource ? 'parameter' : ''}/>
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
