import React, { useCallback, useEffect, useRef, useState, useMemo } from 'react';
import ReactFlow, {
    Panel,
    Background,
    useNodesState,
    useEdgesState,
    useNodes,
    useEdges,
    useReactFlow
} from 'reactflow';
import { Button, Flex, Space, theme } from 'antd';
import { CaretRightOutlined, PartitionOutlined } from '@ant-design/icons';
import { layoutDAG } from '../../graph.ts';
import { Step } from '../Nodes/Step.tsx';
import { Resource } from '../Nodes/Resource.js';
import { useAPI, useAPIMessageLastValue } from '../../hooks/API.ts';
import { NodeConfig } from '../NodeConfig.tsx';
import { Monitor } from '../Monitor.tsx';
import { useNotificationInitializer, useNotification } from '../../hooks/Notification.ts';
import { ReactFlowInstance, BackgroundVariant } from 'reactflow';
import { ActiveOverlay } from '../ActiveOverlay.tsx';
import { Docs } from '../Docs.tsx';

import type { Node, Edge } from 'reactflow';
import { NotFoundFlow } from './NotFoundFlow.tsx';

const { useToken } = theme;
const helpString =
    `
<div align="center">
    <img src="https://github.com/graphbookai/graphbook/blob/main/docs/_static/graphbook.png?raw=true" alt="Graphbook Logo" height="64">
    <h1 style="margin: 0 0 10px 0">Welcome to Graphbook</h1>
    <a href="https://github.com/graphbookai/graphbook">
        <img alt="GitHub Repo stars" src="https://img.shields.io/github/stars/graphbookai/graphbook">
    </a>
</div>

Read only views are currently in beta. Please report any issues to the [repo](https://github.com/graphbookai/graphbook).
`;

export default function ReadOnlyFlow({ filename }) {
    const { token } = useToken();
    const API = useAPI();
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [notificationCtrl, notificationCtxt] = useNotificationInitializer();
    const reactFlowInstance = useRef<ReactFlowInstance | null>(null);
    const graphState = useAPIMessageLastValue("graph_state", filename);
    const isDimensionsInitialized = useRef(false);

    const nodeTypes = useMemo(() => ({
        step: Step,
        resource: Resource,
    }), []);

    useEffect(() => {
        const toReactFlow = (graphState): [Node[], Edge[]] => {
            if (!graphState) {
                return [[], []];
            }

            const nodes: Node[] = [];
            const edges: Edge[] = [];
            Object.entries<any>(graphState).forEach(([nodeId, node]) => {
                Object.values<any>(node.parameters).forEach((param) => {
                    if (param.type !== "resource" && param.default !== undefined && param.value === undefined) {
                        param.value = param.default;
                    }
                });
                const newNode: Node = {
                    id: nodeId,
                    position: {
                        x: 0, y: 0
                    },
                    type: node.type,
                    data: {
                        name: node.name,
                        parameters: node.parameters,
                        isCollapsed: false,
                        category: node.category,
                        properties: {
                            doc: node.doc,
                            defaultTab: node.default_tab
                        }
                    }
                };
                for (const [key, param] of Object.entries<any>(newNode.data.parameters)) {
                    if (param.type === "resource") {
                        edges.push({
                            source: param.value,
                            target: nodeId,
                            sourceHandle: "resource",
                            targetHandle: key,
                            id: `reactflow__edge-${param.value}-${nodeId}${key}`
                        });
                    }
                }
                if (node.type === "step") {
                    newNode.data.inputs = node.inputs.length > 0 ? ["in"] : [];
                    newNode.data.outputs = node.outputs;
                    for (const input of node.inputs) {
                        edges.push({
                            source: input.node,
                            target: nodeId,
                            sourceHandle: input.pin,
                            targetHandle: "in",
                            id: `reactflow__edge-${input.node}${input.pin}-${nodeId}in`
                        });
                    }
                } else if (node.type === "resource") {
                    // do nothing special
                } else {
                    console.error("Unsupported node type: ", node.type);
                }
                nodes.push(newNode);

            });
            return [nodes, edges];
        }

        const [nodes, edges] = toReactFlow(graphState);
        setNodes(nodes);
        setEdges(edges);
        isDimensionsInitialized.current = false;
    }, [graphState]);


    const onInitReactFlow = useCallback((instance) => {
        reactFlowInstance.current = instance;
    }, [reactFlowInstance]);

    const onNodesChangeCallback = useCallback((changes: any[]) => {
        if (isDimensionsInitialized.current) {
            onNodesChange(changes);
            return;
        }
        if (changes.every(change => change.type === 'dimensions')) {
            const mapping = new Map(changes.map(node => [node.id, node.dimensions]));
            const updatedDimensionsNodes = nodes.map(node => ({ ...node, width: mapping.get(node.id)?.width, height: mapping.get(node.id)?.height }));
            const updatedPositionsNodes = layoutDAG(updatedDimensionsNodes, edges);
            const positionChanges = updatedPositionsNodes.map(node => ({ id: node.id, type: 'position', position: node.position, positionAbsolute: node.position }));
            onNodesChange([...changes, ...positionChanges]);
            isDimensionsInitialized.current = true;
        }
    }, [isDimensionsInitialized, nodes, edges, setNodes, onNodesChange]);


    if (!graphState) {
        return <NotFoundFlow />;
    }

    return (
        <div style={{ height: '100%', width: '100%' }}>
            <ActiveOverlay backgroundColor={token.colorBgBase} isActive={API !== null}>
                <ReactFlow
                    key={filename}
                    zoomOnDoubleClick={false}
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={onNodesChangeCallback}
                    onEdgesChange={onEdgesChange}
                    deleteKeyCode={null}
                    onInit={onInitReactFlow}
                    nodeTypes={nodeTypes}
                    nodesConnectable={false}
                    preventScrolling={true}
                >
                    {notificationCtxt}
                    <Space direction="horizontal" align="start" style={{ position: 'absolute', top: '10px', right: '0px', zIndex: 9 }}>
                        <div>
                            <div style={{ position: "absolute", top: 0, left: -10, transform: 'translateX(-100%)' }}>
                                <ControlRow filename={filename} />
                            </div>
                            <Docs helpString={helpString} />
                        </div>
                    </Space>
                    <Panel position='top-left'>
                        <NodeConfig />
                    </Panel>
                    <Monitor />
                    <Background id="1" variant={BackgroundVariant.Lines} gap={20} size={1} color={token.colorBorder} />
                    <Background id="2" variant={BackgroundVariant.Lines} gap={200} size={1} color={token.colorFill} />
                </ReactFlow>
            </ActiveOverlay>
        </div>
    );
}

function ControlRow({ filename }) {
    const size = 'large';
    const runState = useAPIMessageLastValue("run_state", filename);
    const [isRunClicked, setIsRunClicked] = useState(false);
    const API = useAPI();
    const nodes = useNodes();
    const edges = useEdges();
    const { setNodes } = useReactFlow();

    const notification = useNotification();

    const run = useCallback(async () => {
        if (!API) {
            return;
        }

        setIsRunClicked(true);
        const nodeParams = nodes.reduce((acc, node: any) => {
            const params = Object.entries<any>(node.data.parameters).reduce((acc, [key, param]) => {
                acc[key] = param.value;
                return acc;
            }, {});

            acc[node.id] = params;
            return acc;
        }, {});

        API.paramRun(filename, nodeParams);
    }, [API, nodes, filename]);

    const layout = useCallback(() => {
        const newNodes = layoutDAG(nodes, edges);
        setNodes(newNodes);
    }, [nodes, edges, setNodes]);

    return (
        <div className="control-row">
            <Flex gap="small">
                <Button type="default" title="Layout" icon={<PartitionOutlined />} size={size} onClick={layout} disabled={!API} />
                {
                    runState === "initializing" &&
                    <Button type="default" title="Run" icon={<CaretRightOutlined />} size={size} onClick={run} disabled={!API} loading={isRunClicked} />
                }
            </Flex>
        </div>
    );
}
