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
import { Resource } from './Nodes/Resource.js';
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
import { ReactFlowInstance, BackgroundVariant } from 'reactflow';
import { ActiveOverlay } from './ActiveOverlay.tsx';
import { Docs } from './Docs.tsx';

const { useToken } = theme;


type NodeMenu = {
    nodeId: string;
    top: number;
    left: number;
};

type PaneMenu = {
    top: number;
    left: number;
};

export default function ReadOnlyFlow({ filename }) {
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

                // const [nodes, edges] = await onLoadGraph(filename, API);
                // setNodes(nodes);
                // setEdges(edges);
            }
        };

        loadGraph();

    }, [API, filename]);


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



    const onNodeContextMenu = useCallback((event, node) => {
        event.preventDefault();

        setNodeMenu({
            nodeId: node.id,
            top: event.clientY,
            left: event.clientX,
        });
    }, []);


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
                    onNodesChange={onNodesChange}
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
                    <Background id="1" variant={BackgroundVariant.Lines} gap={20} size={1} color={token.colorBorder} />
                    <Background id="2" variant={BackgroundVariant.Lines} gap={200} size={1} color={token.colorFill} />
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
                <Button type="default" title="Layout" icon={<PartitionOutlined />} size={size} onClick={layout} disabled={!API} />
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
