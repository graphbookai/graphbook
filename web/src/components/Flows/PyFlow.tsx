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
import { ClearOutlined, CaretRightOutlined, PauseOutlined, PartitionOutlined, LoadingOutlined } from '@ant-design/icons';
import { layoutDAG, getNodeParams } from '../../graph.ts';
import { Step } from '../Nodes/Step.tsx';
import { Resource } from '../Nodes/Resource.js';
import { NodeContextMenu } from '../ContextMenu.tsx';
import { useAPI, clearNodeLogs } from '../../hooks/API.ts';
import { useRunState } from '../../hooks/RunState.ts';
import { NodeConfig } from '../NodeConfig.tsx';
import { Monitor } from '../Monitor.tsx';
import { useNotificationInitializer } from '../../hooks/Notification.ts';
import { useFilename } from '../../hooks/Filename.ts';
import { ReactFlowInstance, Node, Edge, BackgroundVariant } from 'reactflow';
import { ActiveOverlay } from '../ActiveOverlay.tsx';
import { Docs } from '../Docs.tsx';
import { NotFoundFlow } from './NotFoundFlow.tsx';

const { useToken } = theme;

type NodeMenu = {
    nodeId: string;
    top: number;
    left: number;
};

const NoDocFound = `
### No documentation found.

To add documentation use the Graph.md method.

See our Graphbook docs at https://docs.graphbook.ai
`;

export default function Flow({ filename }) {
    const { token } = useToken();
    const API = useAPI();
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [doc, setDoc] = useState(null);
    const [nodeMenu, setNodeMenu] = useState<NodeMenu | null>(null);
    const [notificationCtrl, notificationCtxt] = useNotificationInitializer();
    const reactFlowInstance = useRef<ReactFlowInstance | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const notFound = useRef(false);

    useEffect(() => {
        const setReactFlow = async () => {
            if (!API) {
                return;
            }

            const graph = await API.getWorkflow(filename);
            if (!graph) {
                notFound.current = true;
                setIsLoading(false);
                setNodes([]);
                setEdges([]);
                return;
            }

            const nodes: Node[] = [];
            const edges: Edge[] = [];
            const { G, doc } = graph;
            Object.entries<any>(G).forEach(([nodeId, node]) => {
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
                        module: node.module,
                        properties: {
                            doc: node.doc,
                            defaultTab: node.default_tab,
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

            notFound.current = false;
            setNodes(nodes);
            setEdges(edges);
            setDoc(doc);
            setIsLoading(false);
        }

        setReactFlow();
    }, [API, filename]);

    useEffect(() => {
        if (isLoading) {
            return;
        }
    
        setTimeout(() => {
            const nodes = reactFlowInstance.current?.getNodes();
            const edges = reactFlowInstance.current?.getEdges();
            if (!nodes || !edges) {
                return;
            }
            const updatedPositionsNodes = layoutDAG(nodes, edges);
            setNodes(updatedPositionsNodes);
        }, 200); // TODO: Currently, no better way to wait for the nodes to be rendered
    }, [isLoading]);

    const nodeTypes = useMemo(() => ({
        step: Step,
        resource: Resource,
        // Unsupported. Cannot serialize yet
        // group: Group,  
        // export: Export,
        // subflow: Subflow,
    }), []);

    const onInitReactFlow = useCallback((instance) => {
        reactFlowInstance.current = instance;
    }, [reactFlowInstance]);

    const onNodesChangeCallback = useCallback((changes: any[]) => {
        onNodesChange(changes);
    }, [onNodesChange]);

    const handleMouseClickComp = useCallback(() => {
        setNodeMenu(null);
    }, []);

    const onNodeContextMenu = useCallback((event, node) => {
        event.preventDefault();

        setNodeMenu({
            nodeId: node.id,
            top: event.clientY,
            left: event.clientX,
        });
    }, []);

    const lineColor1 = token.colorBorder;
    const lineColor2 = token.colorFill;

    if (isLoading) {
        return (
            <Flex style={{ height: '100%', width: '100%' }} justify='center' align='middle'>
                <LoadingOutlined style={{ fontSize: 32 }} />
            </Flex>
        );
    }

    if (notFound.current) {
        return <NotFoundFlow />;
    }

    return (
        <div style={{ height: '100%', width: '100%' }}>
            <ActiveOverlay backgroundColor={token.colorBgBase} isActive={API !== null}>
                <ReactFlow
                    key={filename}
                    onPaneClick={handleMouseClickComp}
                    onNodeClick={handleMouseClickComp}
                    onMove={handleMouseClickComp}
                    zoomOnDoubleClick={false}
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={onNodesChangeCallback}
                    onEdgesChange={onEdgesChange}
                    deleteKeyCode={null}
                    onInit={onInitReactFlow}
                    nodeTypes={nodeTypes}
                    onNodeContextMenu={onNodeContextMenu}
                    nodesConnectable={false}
                    preventScrolling={true}
                >
                    {notificationCtxt}
                    <Space direction="horizontal" align="start" style={{ position: 'absolute', top: '10px', right: '0px', zIndex: 9 }}>
                        <div>
                            <div style={{ position: "absolute", top: 0, left: -10, transform: 'translateX(-100%)' }}>
                                <ControlRow />
                            </div>
                            <Docs doc={doc || NoDocFound} />
                        </div>
                    </Space>
                    <Panel position='top-left'>
                        <NodeConfig />
                    </Panel>
                    <Monitor />
                    {nodeMenu && <NodeContextMenu close={() => setNodeMenu(null)} top={nodeMenu.top} left={nodeMenu.left} nodeId={nodeMenu.nodeId} canEditGraph={false} />}
                    <Background id="1" variant={BackgroundVariant.Lines} gap={20} size={1} color={lineColor1} />
                    <Background id="2" variant={BackgroundVariant.Lines} gap={200} size={1} color={lineColor2} />
                </ReactFlow>
            </ActiveOverlay>
        </div>
    );
}

function ControlRow() {
    const size = 'large';
    const API = useAPI();
    const nodes = useNodes();
    const edges = useEdges();
    const { setNodes } = useReactFlow();
    const filename = useFilename();
    const [runState, runStateShouldChange] = useRunState();

    const run = useCallback(async () => {
        if (!API) {
            return;
        }

        API.pyRunAll(filename, getNodeParams(nodes));
        runStateShouldChange();
    }, [API, nodes, edges, filename]);

    const pause = useCallback(() => {
        if (!API) {
            return;
        }

        API.pause();
        runStateShouldChange();
    }, [API]);

    const clear = useCallback(async () => {
        if (!API) {
            return;
        }

        API.clearAll();
        
        // Also clear logs on the client side
        clearNodeLogs(filename);
    }, [API, filename]);

    const layout = useCallback(() => {
        const newNodes = layoutDAG(nodes, edges);
        setNodes(newNodes);
    }, [nodes, edges, setNodes]);

    const isRunning = useMemo(() => runState === 'running' || runState === 'changing', [runState]);

    return (
        <div className="control-row">
            <Flex gap="small">
                <Button type="default" title="Layout" icon={<PartitionOutlined />} size={size} onClick={layout} disabled={!API} />
                <Button type="default" title="Clear State + Outputs" icon={<ClearOutlined />} size={size} onClick={clear} disabled={isRunning || !API} />
                {
                    isRunning ? (
                        <Button type="default" title="Pause" icon={<PauseOutlined />} size={size} onClick={pause} loading={runState === 'changing'} disabled={!API} />
                    ) : (
                        <Button type="default" title="Run" icon={<CaretRightOutlined />} size={size} onClick={run} disabled={!API} />
                    )
                }
            </Flex>
        </div>
    );
}
