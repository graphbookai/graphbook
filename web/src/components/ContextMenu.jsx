import { Menu } from 'antd';
import { useReactFlow } from 'reactflow';
import { useCallback, useEffect, useState, useMemo } from 'react';
import { keyRecursively } from '../utils';
import { API } from '../api';
import { Graph } from '../graph';

const NODE_OPTIONS = [
    {
        name: 'Run',
        action: (node, reactFlowInstance) => {
            const { getNodes, getEdges } = reactFlowInstance;
            const nodes = getNodes();
            const edges = getEdges();
            const [graph, resources] = Graph.serializeForAPI(nodes, edges);
            API.run(graph, resources, node.id);
        }
    },
    {
        name: 'Step',
        action: (node, reactFlowInstance) => {
            const { getNodes, getEdges } = reactFlowInstance;
            const nodes = getNodes();
            const edges = getEdges();
            const [graph, resources] = Graph.serializeForAPI(nodes, edges);
            API.step(graph, resources, node.id);
        }
    },
    {
        name: 'Clear Outputs',
        action: (node, reactFlowInstance) => {
            const { getNodes, getEdges } = reactFlowInstance;
            const nodes = getNodes();
            const edges = getEdges();
            const [graph, resources] = Graph.serializeForAPI(nodes, edges);
            API.clear(graph, resources, node.id);
        }
    },
    {
        name: 'Duplicate',
        action: (node, reactFlowInstance) => {
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
];

const addExport = (node, reactFlowInstance, isInput, exp) => {
    const currentExports = isInput ? node.data.exports.inputs : node.data.exports.outputs;
    const newExports = {
        [isInput ? 'inputs' : 'outputs']: {
            ...currentExports,
            [`${isInput ? 'in' : 'out'}_${Object.keys(currentExports).length}`]: exp
        }
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

const GROUP_OPTIONS = [
    {
        name: 'Disband Group',
        action: (node, reactFlowInstance) => {
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
                .filter((n) => {console.log(n); return n.id !== node.id})
            );
            setEdges((edges) => edges.filter((e) => e.source !== node.id && e.target !== node.id));
        }
    },
    {
        name: 'Add Step Output Export',
        parent: 'Add Export',
        action: (node, reactFlowInstance) => {
            addExport(node, reactFlowInstance, false, {
                type: 'step'
            });
        }
    },
    {
        name: 'Add Step Input Export',
        action: (node, reactFlowInstance) => {
            addExport(node, reactFlowInstance, true, {
                type: 'step'
            });
        }
    },
    {
        name: 'Add Resource Output Export',
        action: (node, reactFlowInstance) => {
            addExport(node, reactFlowInstance, false, {
                type: 'resource'
            });
        }
    },
    {
        name: 'Add Resource Input Export',
        action: (node, reactFlowInstance) => {
            addExport(node, reactFlowInstance, true, {
                type: 'resource'
            });
        }
    }
]

export function NodeContextMenu({ nodeId, top, left, ...props }) {
    const reactFlowInstance = useReactFlow();
    const node = useMemo(() => reactFlowInstance.getNode(nodeId), [nodeId]);

    const items = useMemo(() => {

            const toReturn = (node.type !== 'group' ? NODE_OPTIONS : GROUP_OPTIONS).map((option) => {
                return {
                    label: typeof option.name === 'function' ? option.name(node) : option.name,
                    children: option.children
                };
            });
            return keyRecursively(toReturn);
        }, [node]);

    const menuItemOnClick = useCallback(({ key }) => {
        const actionIndex = parseInt(key);
        const action = (node.type !== 'group' ? NODE_OPTIONS : GROUP_OPTIONS)[actionIndex].action;
        action(node, reactFlowInstance);
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
    // const nodes = API.getNodes();

    useEffect(() => {
        const setData = async () => {
            const nodes = await API.getNodes();
            setApiNodes(nodes);
        }
        setData();
    }, []);

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
                    inputs: {},
                    outputs: {},
                }
            }
        };
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
            default:
                break;
        }

        close();
    }, [items]);

    return (
        <Menu onClick={onClick} items={items} style={{ top, left, position: 'fixed', zIndex: 10 }} />
    );
}