import { Menu } from 'antd';
import { useReactFlow } from 'reactflow';
import { useCallback, useEffect, useState, useMemo } from 'react';
import { keyRecursively } from '../utils';
import { API } from '../api';
import { Graph } from '../graph';

export function NodeContextMenu({ nodeId, top, left, ...props }) {
  const { getNode, setNodes, addNodes, setEdges } = useReactFlow();
  const items = useMemo(() => {
    const node = getNode(nodeId);
    const toReturn = [{
      label: 'Duplicate',
    }, {
      label: 'Delete',
    }];

    toReturn.push( node.data.isCollapsed ? { label: 'Uncollapse' } : { label: 'Collapse' });
    return keyRecursively(toReturn);
  }, [getNode, nodeId]);

  const duplicateNode = useCallback(() => {
    const node = getNode(nodeId);
    const position = {
      x: node.position.x + 50,
      y: node.position.y + 50,
    };

    addNodes({
      ...node,
      selected: false,
      dragging: false,
      id: `${nodeId}-copy`,
      position,
    });
  }, [getNode, addNodes]);

  const deleteNode = useCallback(() => {
    setNodes((nodes) => nodes.filter((node) => node.id !== nodeId));
    setEdges((edges) => edges.filter((edge) => edge.source !== nodeId && edge.target !== nodeId));
  }, [setNodes, setEdges]);

  const toggleCollapseNode = useCallback(() => {
    const node = getNode(nodeId);

    setNodes((nodes) => {
      return nodes.map((n) => {
        if (n.id === nodeId) {
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
  }, [setNodes]);

  const onClick = useCallback(({ key }) => {
    switch (key) {
        case '1':
            duplicateNode();
            break;
        case '2':
            deleteNode();
            break;
        case '3':
          toggleCollapseNode();
            break;
        default:
            break;
    }
  }, [duplicateNode, deleteNode]);

  return (
    <Menu onClick={onClick} items={items} style={{ top, left, position: 'fixed', zIndex: 10 }} {...props}/>
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
    const type = 'workflowStep';
    Object.values(node.parameters).forEach((p) => {
      p.value = p.default;
    });
    const newNode = ({ type, position, data: node});
    const newNodes = Graph.addNode(newNode, graphNodes);
    setNodes(newNodes);
  }, [graphNodes]);

  const addResource = useCallback((node) => {
    const position = screenToFlowPosition({ x: left, y: top });
    const type = 'resource';
    Object.values(node.parameters).forEach((p) => {
      p.value = p.default;
    });
    const newNode = ({ type, position, data: node});
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
      default:
          break;
    }

    close();
  }, [items]);

  return (
    <Menu onClick={onClick} items={items} style={{ top, left, position: 'fixed', zIndex: 10 }}/>
  );
}