import React, { useCallback, useEffect, useRef, useState, useMemo } from 'react';
import ReactFlow, {
    Panel,
    Background,
    useNodesState,
    useEdgesState,
    addEdge,
    useNodes,
    useEdges,
    useReactFlow
} from 'reactflow';
import { Button, Flex, Space, theme } from 'antd';
import { ClearOutlined, CaretRightOutlined, PauseOutlined, PartitionOutlined } from '@ant-design/icons';
import { Graph, layoutDAG } from '../graph.ts';
import { SearchNode } from './SearchNode.tsx';
import { Step } from './Nodes/Step.tsx';
import { Group, groupIfPossible } from './Nodes/Group.tsx';
import { getHandle, evalDragData } from '../utils.ts';
import { Resource } from './Nodes/Resource.jsx';
import { Export } from './Nodes/Export.tsx';
import { NodeContextMenu, PaneContextMenu } from './ContextMenu.tsx';
import { useAPI, useAPIMessage } from '../hooks/API.ts';
import { useRunState } from '../hooks/RunState.ts';
import { GraphStore } from '../graphstore.ts';
import { NodeConfig } from './NodeConfig.tsx';
import { Subflow } from './Nodes/Subflow.tsx';
import { Monitor } from './Monitor.tsx';
import { useNotificationInitializer, useNotification } from '../hooks/Notification.ts';
import { SerializationErrorMessages } from './Errors.tsx';
import { useFilename } from '../hooks/Filename.ts';
import { ReactFlowInstance, Node, Edge, BackgroundVariant } from 'reactflow';
import { ActiveOverlay } from './ActiveOverlay.tsx';
import { Docs } from './Docs.tsx';

const { useToken } = theme;
const makeDroppable = (e) => e.preventDefault();
const onLoadGraph = async (filename, API): Promise<[Node[], Edge[]]> => {
    const file = await API.getFile(filename);
    if (file?.content) {
        const graph = JSON.parse(file.content);
        if (graph.type === 'workflow') {
            return Graph.parseGraph(graph, API);
        }
    }
    return [[], []];
};

type NodeMenu = {
    nodeId: string;
    top: number;
    left: number;
};

type PaneMenu = {
    top: number;
    left: number;
};

export default function Flow({ filename }) {
    const { token } = useToken();
    const API = useAPI();
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [nodeMenu, setNodeMenu] = useState<NodeMenu | null>(null);
    const [paneMenu, setPaneMenu] = useState<PaneMenu | null>(null);
    const [searchMenu, setSearchMenu] = useState<PaneMenu | null>(null);
    const [runState, _] = useRunState();
    const graphStore = useRef<GraphStore | null>(null);
    const [notificationCtrl, notificationCtxt] = useNotificationInitializer();
    const reactFlowInstance = useRef<ReactFlowInstance | null>(null);

    useEffect(() => {
        const loadGraph = async () => {
            if (API) {
                /* Setting to empty so that Reactflow's internal edge rendering system is refreshed */
                setNodes([]);
                setEdges([]);

                const [nodes, edges] = await onLoadGraph(filename, API);
                setNodes(nodes);
                setEdges(edges);
                graphStore.current = new GraphStore(filename, API!, nodes, edges);
            }
        };

        graphStore.current = null;
        loadGraph();

    }, [API, filename]);

    useEffect(() => {
        const searchListener = (e) => {
            if (e.key === ' ' && e.ctrlKey) {
                setSearchMenu({
                    top: window.innerHeight / 2 - 200,
                    left: window.innerWidth / 2
                });
            }
        };

        document.addEventListener('keydown', searchListener);
        return () => {
            document.removeEventListener('keydown', searchListener);
        };
    }, []);

    const nodeTypes = useMemo(() => ({
        step: Step,
        resource: Resource,
        group: Group,
        export: Export,
        subflow: Subflow,
    }), []);

    const onInitReactFlow = useCallback((instance) => {
        reactFlowInstance.current = instance;
    }, [reactFlowInstance]);

    const onNodesChangeCallback = useCallback((changes) => {
        if (runState !== 'stopped') {
            const newChanges = changes.filter(change => change.type !== 'remove');
            if (newChanges.length !== changes.length) {
                notificationCtrl.error({
                    key: 'no-remove',
                    message: 'Remove Disabled',
                    description: 'Cannot remove nodes while running the graph',
                    duration: 1,
                });
            }
            return onNodesChange(newChanges);
        }
        onNodesChange(changes);
    }, [runState]);

    const onEdgesChangeCallback = useCallback((changes) => {
        if (runState !== 'stopped') {
            const newChanges = changes.filter(change => change.type !== 'remove');
            if (newChanges.length !== changes.length) {
                notificationCtrl.error({
                    key: 'no-remove',
                    message: 'Remove Disabled',
                    description: 'Cannot remove edges while running the graph',
                    duration: 1,
                });
            }
            return onEdgesChange(newChanges);
        }
        onEdgesChange(changes);
    }, [runState]);

    const onConnect = useCallback((params) => {
        const targetNode = nodes.find(n => n.id === params.target);
        const sourceNode = nodes.find(n => n.id === params.source);
        if (!targetNode || !sourceNode) {
            return;
        }
        const targetHandle = getHandle(targetNode, params.targetHandle, true);
        const sourceHandle = getHandle(sourceNode, params.sourceHandle, false);
        const edge = {
            ...params,
            data: {
                properties: {
                    targetHandle,
                    sourceHandle,
                    type: sourceHandle.type,
                }
            }
        };
        setEdges((eds) => addEdge(edge, eds));
    }, [setEdges, edges, nodes]);

    const onNodesDelete = useCallback((deletedNodes) => {
        const deletedNodesMap = {};
        deletedNodes.forEach(node => {
            deletedNodesMap[node.id] = node;
        });
        nodes.forEach(n => {
            if (n.parentId) {
                const parent = deletedNodesMap[n.parentId];
                if (parent) {
                    n.parentId = undefined;
                    n.position = { x: n.position.x + parent.position.x, y: n.position.y + parent.position.y };
                }
            }
        });
    }, []);

    useEffect(() => {
        if (graphStore.current) {
            graphStore.current.update(nodes, edges);
        }
    }, [nodes, edges, graphStore]);

    const handleMouseClickComp = useCallback(() => {
        setSearchMenu(null);
        setNodeMenu(null);
        setPaneMenu(null);
    }, []);

    const onPaneDoubleClick = useCallback((event) => {
        const isANodeSelected = nodes.some(node => node.selected);

        if (!isANodeSelected) {
            setSearchMenu({
                top: event.clientY,
                left: event.clientX
            });
        }
    }, [nodes]);

    const onDrop = useCallback((event) => {
        if (!reactFlowInstance.current || !API) {
            return;
        }
        evalDragData(reactFlowInstance.current, API, event);
    }, [reactFlowInstance, API]);

    const onNodeContextMenu = useCallback((event, node) => {
        event.preventDefault();

        setNodeMenu({
            nodeId: node.id,
            top: event.clientY,
            left: event.clientX,
        });
    }, []);

    const onPaneContextMenu = useCallback((event) => {
        event.preventDefault();

        setPaneMenu({
            top: event.clientY,
            left: event.clientX
        });
    }, []);

    const isValidConnection = useCallback((connection) => {
        if (!reactFlowInstance.current) {
            return false;
        }
        const { getNode, getNodes, getEdges } = reactFlowInstance.current;
        const srcNode = getNode(connection.source);
        const tgtNode = getNode(connection.target);
        if (!srcNode || !tgtNode) {
            return false;
        }
        const srcHandle = getHandle(srcNode, connection.sourceHandle, false);
        const tgtHandle = getHandle(tgtNode, connection.targetHandle, true);

        if (!srcHandle || !tgtHandle) {
            return false;
        }

        if (srcHandle.type !== tgtHandle.type) {
            return false;
        }

        if (srcHandle.nodeType === 'group') {
            if (srcHandle.inner && tgtNode.parentId !== srcNode.id) {
                return false;
            }
            if (!srcHandle.inner && tgtNode.parentId === srcNode.id) {
                return false;
            }
        }

        if (tgtHandle.nodeType === 'group') {
            if (tgtHandle.inner && srcNode.parentId !== tgtNode.id) {
                return false;
            }
            if (!tgtHandle.inner && srcNode.parentId === tgtNode.id) {
                return false;
            }
        }

        if (srcNode.type === 'export' && tgtNode.type === 'export') {
            return false;
        }

        const edges = getEdges();
        if (tgtHandle.type === 'resource') {
            for (const edge of edges) {
                if (edge.target === connection.target && edge.targetHandle === connection.targetHandle) {
                    return false;
                }
            }
        }

        if (Graph.wouldBeCyclic(getNodes(), edges, connection)) {
            notificationCtrl.error({
                key: 'no-cycles',
                message: 'No Cycles',
                description: 'Graphbook only supports DAGs',
                duration: 1,
            });
            return false;
        }

        return true;
    }, [reactFlowInstance]);

    const nodeUpdatedCallback = useCallback(async () => {
        if (!API) {
            return;
        }

        const searchNodes = (catalogue, name, category) => {
            if (!category) {
                return null;
            }
            const categories = category.split('/');
            let c = catalogue[categories[0]];
            for (let i = 1; i < categories.length; i++) {
                c = c?.children[categories[i]];
            }
            if (!c) {
                return null;
            }
            return c.children?.[name];
        };

        const updatedNodes = await API.getNodes();

        setNodes(nodes => {
            const mergedNodes = nodes.map(node => {
                const updatedNodeData = (
                    node.type === 'step' ?
                        searchNodes(updatedNodes.steps, node.data.name, node.data.category) :
                        searchNodes(updatedNodes.resources, node.data.name, node.data.category)
                );
                if (updatedNodeData) {
                    // Create a new parameters object by keeping only the common parameters between the old and new
                    const newParameters = Object.keys(updatedNodeData.parameters).reduce((acc, key) => {
                        if (node.data.parameters.hasOwnProperty(key)) {
                            acc[key] = node.data.parameters[key];
                        } else {
                            acc[key] = updatedNodeData.parameters[key];
                        }
                        return acc;
                    }, {});

                    return {
                        ...node,
                        data: {
                            ...node.data,
                            ...updatedNodeData,
                            parameters: {
                                ...newParameters,
                            },
                        },
                    };
                }
                return node;
            });
            return mergedNodes
        });
    }, [setNodes, API]);

    useAPIMessage('node_updated', nodeUpdatedCallback);

    const lineColor1 = token.colorBorder;
    const lineColor2 = token.colorFill;

    const onNodeDragStop = useCallback((e, _, draggedNodes) => {
        const updatedNodes = groupIfPossible(draggedNodes, nodes);
        if (graphStore.current) {
            graphStore.current.updateNodePositions(updatedNodes);
        }
        setNodes(updatedNodes);
    }, [nodes]);

    return (
        <div style={{ height: '100%', width: '100%' }}>
            <ActiveOverlay backgroundColor={token.colorBgBase} isActive={API !== null}>
                <ReactFlow
                    key={filename}
                    onDoubleClick={onPaneDoubleClick}
                    onPaneClick={handleMouseClickComp}
                    onNodeClick={handleMouseClickComp}
                    onMove={handleMouseClickComp}
                    zoomOnDoubleClick={false}
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={onNodesChangeCallback}
                    onEdgesChange={onEdgesChangeCallback}
                    onConnect={onConnect}
                    deleteKeyCode={"Delete"}
                    onInit={onInitReactFlow}
                    nodeTypes={nodeTypes}
                    onDrop={onDrop}
                    onDragOver={makeDroppable}
                    onDragEnter={makeDroppable}
                    onNodeContextMenu={onNodeContextMenu}
                    onPaneContextMenu={onPaneContextMenu}
                    isValidConnection={isValidConnection}
                    onNodeDragStop={onNodeDragStop}
                    onNodesDelete={onNodesDelete}
                    preventScrolling={true}
                >
                    {notificationCtxt}
                    <Space direction="horizontal" align="start" style={{ position: 'absolute', top: '10px', right: '0px', zIndex: 9 }}>
                        <div>
                            <div style={{ position: "absolute", top: 0, left: -10, transform: 'translateX(-100%)' }}>
                                <ControlRow />
                            </div>
                            <Docs />
                        </div>
                    </Space>
                    <Panel position='top-left'>
                        <NodeConfig />
                    </Panel>
                    <Monitor />
                    {nodeMenu && <NodeContextMenu close={() => setNodeMenu(null)} top={nodeMenu.top} left={nodeMenu.left} nodeId={nodeMenu.nodeId} />}
                    {paneMenu && <PaneContextMenu close={() => setPaneMenu(null)} top={paneMenu.top} left={paneMenu.left} />}
                    {searchMenu && <SearchNode close={() => setSearchMenu(null)} top={searchMenu.top} left={searchMenu.left} />}
                    <Background id="1" variant={BackgroundVariant.Lines} gap={20} size={1} color={lineColor1} />
                    <Background id="2" variant={BackgroundVariant.Lines} gap={200} size={1} color={lineColor2} />
                </ReactFlow>
            </ActiveOverlay>
        </div>
    );
}

function ControlRow() {
    const size = 'large';
    const [runState, runStateShouldChange] = useRunState();
    const API = useAPI();
    const nodes = useNodes();
    const edges = useEdges();
    const { setNodes } = useReactFlow();
    const notification = useNotification();
    const filename = useFilename();

    const run = useCallback(async () => {
        if (!API) {
            return;
        }
        const [[graph, resources], errors] = await Graph.serializeForAPI(nodes, edges);
        if (errors.length > 0) {
            notification.error({
                key: 'invalid-graph',
                message: 'Invalid Graph',
                description: <SerializationErrorMessages errors={errors} />,
                duration: 3,
            })
            return;
        }
        API.runAll(graph, resources, filename);
        runStateShouldChange();
    }, [API, nodes, edges, notification, filename]);

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
    }, [API]);

    const layout = useCallback(() => {
        const newNodes = layoutDAG(nodes, edges);
        setNodes(newNodes);
    }, [nodes, edges, setNodes]);

    return (
        <div className="control-row">
            <Flex gap="small">
                <Button type="default" title="Layout" icon={<PartitionOutlined />} size={size} onClick={layout} disabled={runState !== 'stopped' || !API} />
                <Button type="default" title="Clear State + Outputs" icon={<ClearOutlined />} size={size} onClick={clear} disabled={runState !== 'stopped' || !API} />
                {
                    runState !== 'stopped' ? (
                        <Button type="default" title="Pause" icon={<PauseOutlined />} size={size} onClick={pause} loading={runState === 'changing'} disabled={!API} />
                    ) : (
                        <Button type="default" title="Run" icon={<CaretRightOutlined />} size={size} onClick={run} disabled={!API} />
                    )
                }
            </Flex>
        </div>
    );
}
