import { Menu } from 'antd';
import { useReactFlow, useUpdateNodeInternals } from 'reactflow';
import { useCallback, useEffect, useState, useMemo } from 'react';
import { keyRecursively, uniqueIdFrom } from '../utils';
import { Graph } from '../graph';
import { useRunState } from '../hooks/RunState';
import { useAPI } from '../hooks/API';

export function NodeContextMenu({ nodeId, top, left, ...props }) {
    const reactFlowInstance = useReactFlow();
    const node = useMemo(() => reactFlowInstance.getNode(nodeId), [nodeId]);
    const [runState, runStateShouldChange] = useRunState();
    const API = useAPI();
    const updateNodeInternals = useUpdateNodeInternals();

    const NODE_OPTIONS = useMemo(() => [
        {
            name: 'Run',
            disabled: (runState) => API && runState !== 'stopped',
            action: async () => {
                const { getNodes, getEdges } = reactFlowInstance;
                const nodes = getNodes();
                const edges = getEdges();
                const [graph, resources] = await Graph.serializeForAPI(nodes, edges);
                API.run(graph, resources, node.id);
                runStateShouldChange();
            }
        },
        {
            name: 'Step',
            disabled: (runState) => API && runState !== 'stopped',
            action: async () => {
                const { getNodes, getEdges } = reactFlowInstance;
                const nodes = getNodes();
                const edges = getEdges();
                const [graph, resources] = await Graph.serializeForAPI(nodes, edges);
                API.step(graph, resources, node.id);
                runStateShouldChange();
            }
        },
        {
            name: 'Clear Outputs',
            disabled: (runState) => API && runState !== 'stopped',
            action: async () => {
                const { getNodes, getEdges } = reactFlowInstance;
                const nodes = getNodes();
                const edges = getEdges();
                const [graph, resources] = await Graph.serializeForAPI(nodes, edges);
                API.clear(graph, resources, node.id);
            }
        },
        {
            name: 'Duplicate',
            disabled: (runState) => runState !== 'stopped',
            action: () => {
                const { addNodes } = reactFlowInstance;
                const position = {
                    x: node.position.x + 50,
                    y: node.position.y + 50,
                };
    
                addNodes({
                    ...node,
                    selected: false,
                    dragging: false,
                    id: `${node.id}-copy`,
                    position,
                });
            }
        },
        {
            name: 'Delete',
            disabled: (runState) => runState !== 'stopped',
            action: (node, reactFlowInstance) => {
                const { setNodes, setEdges } = reactFlowInstance;
                setNodes((nodes) => nodes.filter((n) => n.id !== node.id));
                setEdges((edges) => edges.filter((e) => e.source !== node.id && e.target !== node.id));
            }
        },
        {
            name: (node) => node.data.isCollapsed ? 'Uncollapse' : 'Collapse',
            action: (node, reactFlowInstance) => {
                const { setNodes } = reactFlowInstance;
                setNodes((nodes) => {
                    return nodes.map((n) => {
                        if (n.id === node.id) {
                            return {
                                ...n,
                                data: {
                                    ...n.data,
                                    isCollapsed: !node.data.isCollapsed
                                }
                            };
                        }
                        return n;
                    });
                });
            }
        }
    ], [node, reactFlowInstance, runState, runStateShouldChange, API]);
    
    const GROUP_OPTIONS = useMemo(() => {
        const addExport = (isInput, exp) => {
            const currentExports = isInput ? node.data.exports.inputs : node.data.exports.outputs;
            const id = uniqueIdFrom(currentExports);
            const newExports = {
                [isInput ? 'inputs' : 'outputs']: [
                    ...currentExports,
                    {
                        id,
                        ...exp
                    }
                ]
            };
            const { setNodes } = reactFlowInstance;
            setNodes(nodes => nodes.map(n => {
                if (n.id === node.id) {
                    return {
                        ...n,
                        data: {
                            ...n.data,
                            exports: {
                                ...n.data.exports,
                                ...newExports
                            }
                        }
                    }
                }
                return n;
            }));
        };
        return [{
            name: 'Disband Group',
            disabled: (runState) => runState !== 'stopped',
            action: () => {
                const { setNodes, setEdges } = reactFlowInstance;
                setNodes((nodes) => nodes
                    .map((n) => {
                        if (n.parentId === node.id) {
                            return {
                                ...n,
                                parentId: null,
                                position: { x: n.position.x + node.position.x, y: n.position.y + node.position.y }
                            };
                        }
                        return n;
                    })
                    .filter((n) => n.id !== node.id)
                );
                setEdges((edges) => edges.filter((e) => e.source !== node.id && e.target !== node.id));
            }
        },
        {
            name: 'Add Step Input Export',
            action: () => {
                addExport(true, {
                    name: 'in',
                    type: 'step'
                });
            }
        },
        {
            name: 'Add Resource Input Export',
            action: () => {
                addExport(true, {
                    name: 'resource',
                    type: 'resource'
                });
            }
        },
        {
            name: 'Add Step Output Export',
            parent: 'Add Export',
            action: () => {
                addExport(false, {
                    name: 'out',
                    type: 'step'
                });
            }
        },
        {
            name: 'Add Resource Output Export',
            action: () => {
                addExport(false, {
                    name: 'resource',
                    type: 'resource'
                });
            }
        },
        {
            name: node => node.data.isCollapsed ? 'Uncollapse' : 'Collapse',
            action: () => {
                const { setNodes } = reactFlowInstance;
                setNodes((nodes) => {
                    return nodes.map((n) => {
                        if (n.parentId === node.id) {
                            return {
                                ...n,
                                hidden: !node.data.isCollapsed
                            };
                        } else if (n.id === node.id) {
                            return {
                                ...n,
                                data: {
                                    ...n.data,
                                    isCollapsed: !node.data.isCollapsed
                                }
                            };
                        }
                        return n;
                    });
                });
            }
        }];
    }, [node, reactFlowInstance]);

    const EXPORT_OPTIONS = useMemo(() => [
        {
            name: 'Edit Label',
            action: () => {
                const { setNodes } = reactFlowInstance;
                setNodes((nodes) => {
                    return nodes.map((n) => {
                        if (n.id === node.id) {
                            return {
                                ...n,
                                data: {
                                    ...n.data,
                                    isEditing: true
                                }
                            };
                        }
                        return n;
                    });
                });
            }
        }
    ], [node, reactFlowInstance]);
    
    const getOptions = (nodeType) => {
        if (nodeType === 'group') {
            return GROUP_OPTIONS;
        }
        if (nodeType === 'export') {
            return EXPORT_OPTIONS;
        }
        if (nodeType === 'step' || nodeType === 'resource') {
            return NODE_OPTIONS;
        }
    };

    const items = useMemo(() => {
        const toReturn = getOptions(node.type).map((option) => {
            return {
                label: typeof option.name === 'function' ? option.name(node) : option.name,
                children: option.children,
                disabled: typeof option.disabled === 'function' ? option.disabled(runState) : option.disabled,
            };
        });
        return keyRecursively(toReturn);
    }, [node]);

    const menuItemOnClick = useCallback(({ key }) => {
        const actionIndex = parseInt(key);
        const action = getOptions(node.type)[actionIndex].action;
        action();
        updateNodeInternals(nodeId);
    }, [node]);

    return (
        <Menu onClick={menuItemOnClick} items={items} style={{ top, left, position: 'fixed', zIndex: 10 }} {...props} />
    );
}

function getEvent(items, key) {
    const findItem = (item, key) => {
        if (item.key == key) {
            return item;
        }
        if (item.children) {
            for (let child of item.children) {
                let foundItem = findItem(child, key);
                if (foundItem) {
                    return foundItem;
                }
            }
        }
        return null;
    }

    for (const item in items) {
        const foundItem = findItem(items[item], key);
        if (foundItem) {
            return { event: items[item].label, item: foundItem }
        }
    }

    return { event: null, item: null };
}

export function PaneContextMenu({ top, left, close }) {
    const { setNodes, getNodes, screenToFlowPosition } = useReactFlow();
    const [apiNodes, setApiNodes] = useState({ steps: {}, resources: {} });
    const graphNodes = getNodes();
    const API = useAPI();

    useEffect(() => {
        const setData = async () => {
            const nodes = await API.getNodes();
            setApiNodes(nodes);
        };
        if (API) {
            setData();
        }
    }, [API]);

    const items = useMemo(() => {
        const { steps, resources } = apiNodes;
        // Convert Dict Tree to List Tree
        const toListTree = (dictTree) => {
            const listTree = [];
            for (const key in dictTree) {
                const node = dictTree[key];
                const listItem = {
                    ...node,
                    label: key,
                }
                if (node.children) {
                    listItem.children = toListTree(node.children);
                }
                listTree.push(listItem);
            }
            return listTree;
        };

        const items = [{
            label: 'Add Step',
            children: toListTree(steps),
        }, {
            label: 'Add Resource',
            children: toListTree(resources)
        }, {
            label: 'Add Group'
        }, {
            label: 'Add Export',
            children: [{
                label: 'Resource Input',
                key: 'resource input'
            }, {
                label: 'Step Input',
                key: 'step input'
            }, {
                label: 'Resource Output',
                key: 'resource output'
            }, {
                label: 'Step Output',
                key: 'step output'
            }]
        }];

        return keyRecursively(items);
    }, [apiNodes]);

    const addStep = useCallback((node) => {
        const position = screenToFlowPosition({ x: left, y: top });
        const type = 'step';
        Object.values(node.parameters).forEach((p) => {
            p.value = p.default;
        });
        const newNode = ({ type, position, data: node });
        const newNodes = Graph.addNode(newNode, graphNodes);
        setNodes(newNodes);
    }, [graphNodes]);

    const addResource = useCallback((node) => {
        const position = screenToFlowPosition({ x: left, y: top });
        const type = 'resource';
        Object.values(node.parameters).forEach((p) => {
            p.value = p.default;
        });
        const newNode = ({ type, position, data: node });
        const newNodes = Graph.addNode(newNode, graphNodes);
        setNodes(newNodes);
    }, [graphNodes]);

    const addGroup = useCallback(() => {
        const position = screenToFlowPosition({ x: left, y: top });
        const type = 'group';
        const newNode = {
            type,
            position,
            width: 200,
            height: 200,
            data: {
                label: 'Group',
                exports: {
                    inputs: [],
                    outputs: [],
                }
            }
        };
        const newNodes = Graph.addNode(newNode, graphNodes);
        setNodes(newNodes);
    }, [graphNodes]);

    const addExport = useCallback((exportType, isResource) => {
        const position = screenToFlowPosition({ x: left, y: top });
        const type = 'export';
        const label = isResource ? 'Resource' : (exportType === 'input' ? 'Input' : 'Output');
        const newNode = ({ type, position, data: { label, exportType, isResource } });
        const newNodes = Graph.addNode(newNode, graphNodes);
        setNodes(newNodes);
    }, [graphNodes]);

    const onClick = useCallback(({ key }) => {
        const { event, item } = getEvent(items, key);
        switch (event) {
            case 'Add Step':
                addStep(item);
                break;
            case 'Add Resource':
                addResource(item);
                break;
            case 'Add Group':
                addGroup();
                break;
            case 'Add Export':
                if (item.label === 'Resource Input') {
                    addExport('input', true);
                } else if (item.label === 'Step Input') {
                    addExport('input', false);
                } else if (item.label === 'Resource Output') {
                    addExport('output', true);
                } else if (item.label === 'Step Output') {
                    addExport('output', false);
                }
                break;
            default:
                break;
        }

        close();
    }, [items]);

    return (
        <Menu onClick={onClick} items={items} style={{ top, left, position: 'fixed', zIndex: 10 }} />
    );
}