import React, { useCallback, useEffect, useRef, useState, useMemo } from 'react';
import ReactFlow, {
    Panel,
    Background,
    useNodesState,
    useEdgesState,
    addEdge
} from 'reactflow';
import { Button, Flex, Typography, notification, theme } from 'antd';
import { ClearOutlined, CaretRightOutlined, PauseOutlined } from '@ant-design/icons';
import { Graph } from '../graph';
import AddNode from './AddNode';
import { WorkflowStep } from './Nodes/Node.jsx';
import { Group, groupIfPossible } from './Nodes/Group.tsx';
import { getHandle, filesystemDragEnd } from '../utils.ts';
import { Resource } from './Nodes/Resource.jsx';
import { Export } from './Nodes/Export.tsx';
import { NodeContextMenu, PaneContextMenu } from './ContextMenu';
import { useAPI } from '../hooks/API.ts';
import { useRunState } from '../hooks/RunState';
import { GraphStore } from '../graphstore.ts';
import { NodeConfig } from './NodeConfig.tsx';
import { Subflow } from './Nodes/Subflow.tsx';
const { Text } = Typography;
const { useToken } = theme;
const makeDroppable = (e) => e.preventDefault();
const onLoadGraph = async (filename, API) => {
    const file = await API.getFile(filename);
    if (file?.content) {
        const graph = JSON.parse(file.content);
        if (graph.type === 'workflow') {
            for (const node of graph.nodes) {
                if (node.type === 'subflow' && node.data.filename !== filename) {
                    const file = await API.getFile(node.data.filename);
                    const subflowGraph = JSON.parse(file?.content);
                    node.data.properties = {
                        nodes: subflowGraph.nodes,
                        edges: subflowGraph.edges,
                    };
                }
            }
            return [graph.nodes, graph.edges];
        }
    }
    return [[], []];
};

export default function Flow({ filename }) {
    const { token } = useToken();
    const API = useAPI();
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [nodeMenu, setNodeMenu] = useState(null);
    const [paneMenu, setPaneMenu] = useState(null);
    const [runState, _] = useRunState();
    const [isLoading, setIsLoading] = useState(true); // TODO
    const graphStore = useRef(null);

    const [notificationCtrl, notificationCtxt] = notification.useNotification({ maxCount: 1 });
    // Coalesce
    const [isAddNodeActive, setIsAddNodeActive] = useState(false);
    const [eventMousePos, setEventMousePos] = useState({ x: 0, y: 0 });
    const [nodeToPos, setNodeToPos] = useState({ x: 0, y: 0 });
    const reactFlowInstance = useRef(null);
    const reactFlowRef = useRef(null);
    

    useEffect(() => {
        graphStore.current = null;
    }, [filename]);

    useEffect(() => {
        const loadGraph = async () => {
            const [nodes, edges] = await onLoadGraph(filename, API);
            console.log(nodes, edges);
            setNodes(nodes);
            setEdges(edges);
            graphStore.current = new GraphStore(filename, API, nodes, edges);
        };
        graphStore.current = null;

        if (!filename || !API) {
            setNodes([]);
            setEdges([]);
        } else {
            loadGraph();
        }
    }, [API, filename]);

    const nodeTypes = useMemo(() => ({
        step: WorkflowStep,
        resource: Resource,
        group: Group,
        export: Export,
        subflow: Subflow,
    }), []);

    const onInitReactFlow = (instance) => {
        reactFlowInstance.current = instance;
    };

    const onNodesChangeCallback = useCallback((changes) => {
        setIsAddNodeActive(false);
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
    });

    const onEdgesChangeCallback = useCallback((changes) => {
        setIsAddNodeActive(false);
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
    });

    const onConnect = useCallback((params) => {
        setEdges((eds) => addEdge(params, eds));
    }, [setEdges, edges]);

    const onNodesDelete = useCallback((deletedNodes) => {
        const deletedNodesMap = {};
        deletedNodes.forEach(node => {
            deletedNodesMap[node.id] = node;
        });
        nodes.forEach(n => {
            if (n.parentId) {
                const parent = deletedNodesMap[n.parentId];
                if (parent) {
                    n.parentId = null;
                    n.position = { x: n.position.x + parent.position.x, y: n.position.y + parent.position.y };
                }
            }
        });
    });

    useEffect(() => {
        if (graphStore.current) {
            graphStore.current.update(nodes, edges);
        }
    }, [nodes, edges, API, filename]);

    const handleMouseClickComp = useCallback((event) => {
        setIsAddNodeActive(false);
        setNodeMenu(null);
        setPaneMenu(null);
        if (!event) {
            return;
        }
        if (event.type === 'dblclick' && !isAddNodeActive) {
            setIsAddNodeActive(true);
            setEventMousePos({ x: event.clientX, y: event.clientY });
            setNodeToPos(reactFlowInstance.current.screenToFlowPosition({ x: event.clientX, y: event.clientY }));
        }
    });

    const handleMouseClick = useCallback((event) => {
        if (event.type === 'click') {
            setNodeMenu(null);
            setPaneMenu(null);
        }
    }, [reactFlowInstance]);

    useEffect(() => {
        document.addEventListener('click', handleMouseClick);
        return () => {
            document.removeEventListener('click', handleMouseClick);
        };
    }, [handleMouseClick]);

    const getGraph = useCallback(async () => {
        return await Graph.serializeForAPI(nodes, edges);
    }, [nodes, edges]);

    const onDrop = useCallback((event) => {
        filesystemDragEnd(reactFlowInstance.current, API, event);
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
        const { getNode, getNodes, getEdges } = reactFlowInstance.current;
        const srcNode = getNode(connection.source);
        const tgtNode = getNode(connection.target);
        const srcHandle = getHandle(srcNode, connection.sourceHandle, false);
        const tgtHandle = getHandle(tgtNode, connection.targetHandle, true);

        if (!srcHandle || !tgtHandle) {
            return false;
        }

        if (srcHandle.type !== tgtHandle.type) {
            return false;
        }

        if (srcHandle.nodeType === 'group' && srcHandle.inner) {
            if (tgtNode.parentId !== srcNode.id) {
                return false;
            }
        }

        if (tgtHandle.nodeType === 'group' && tgtHandle.inner) {
            if (srcNode.parentId !== tgtNode.id) {
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

    useEffect(() => {
        if (!API) {
            return;
        }
        // Add WebSocket event listener for node updates
        const handleNodeUpdate = async (event) => {
            const message = JSON.parse(event.data);
            if (message.event !== 'node_updated') {
                return;
            }

            const updatedNodes = await API.getNodes();
            const mergedNodes = nodes.map(node => {
                const updatedNodeData = updatedNodes.steps[node.data.category]?.children[node.data.name];
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

            setNodes(mergedNodes);
        };

        API.addWsEventListener('message', handleNodeUpdate);

        return () => {
            API.removeWsEventListener('message', handleNodeUpdate);
        };
    }, [nodes, setNodes, API]);

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
            <ReactFlow
                ref={reactFlowRef}
                onPaneClick={handleMouseClickComp}
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
            >
                {notificationCtxt}
                <Panel position='top-right'>
                    <ControlRow getGraph={getGraph} />
                </Panel>
                <Panel position='top-left'>
                    <NodeConfig />
                </Panel>
                <Panel position='bottom-left'>
                    <Text italic>{filename}</Text>
                </Panel>
                {nodeMenu && <NodeContextMenu {...nodeMenu} />}
                {paneMenu && <PaneContextMenu onClick={handleMouseClickComp} close={() => setPaneMenu(null)} {...paneMenu} />}
                <Background id="1" variant="lines" gap={10} size={1} color={lineColor1} />
                <Background id="2" variant="lines" gap={100} color={lineColor2} />
            </ReactFlow>
            {isAddNodeActive && <AddNode position={eventMousePos} setNodeTo={nodeToPos} />}
        </div>
    );
}

function ControlRow({ getGraph }) {
    const size = 'large';
    const [runState, runStateShouldChange] = useRunState();
    const API = useAPI();

    const run = useCallback(async () => {
        const [graph, resources] = await getGraph();
        API.runAll(graph, resources);
        runStateShouldChange();
    });

    const pause = useCallback(() => {
        API.pause();
        runStateShouldChange();
    });

    const clear = useCallback(() => {
        const [graph, resources] = getGraph();
        API.clearAll(graph, resources);
    });

    return (
        <div className="control-row">
            <Flex gap="small" wrap="wrap">
                <Button type="default" icon={<ClearOutlined />} size={size} onClick={clear} disabled={runState !== 'stopped'} /> {/* Clear */}
                {
                    runState !== 'stopped' ? (
                        <Button type="default" icon={<PauseOutlined />} size={size} onClick={pause} loading={runState === 'changing'} />
                    ) : (
                        <Button type="default" icon={<CaretRightOutlined />} size={size} onClick={run} loading={runState === 'changing'} />
                    )
                }
            </Flex>
        </div>
    );
}
