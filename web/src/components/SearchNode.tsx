import React, { useCallback, useRef, useEffect, useState, useMemo } from 'react';
import { useReactFlow } from 'reactflow';
import { Input, List, Card, Typography, theme } from 'antd';
import { API } from '../api';
import { Graph } from '../graph';
import type { InputRef } from 'antd';
const { Text } = Typography;
const { Search } = Input;

export function SearchNode({ top, left, close }) {
    const searchRef = useRef<InputRef>(null);
    const [searchText, setSearchText] = useState('');
    const { setNodes, getNodes, screenToFlowPosition } = useReactFlow();
    const graphNodes = getNodes();

    useEffect(() => {
        if (searchRef.current) {
            searchRef.current.focus();
        }
    }, [searchRef]);

    const onInputChange = (e) => {
        setSearchText(e.target.value);
    };

    const addStep = useCallback((node) => {
        const position = screenToFlowPosition({ x: left, y: top });
        const type = 'step';
        Object.values<any>(node.parameters).forEach((p) => {
            p.value = p.default;
        });
        const newNode = ({ type, position, data: node });
        const newNodes = Graph.addNode(newNode, graphNodes);
        setNodes(newNodes);
        close();
    }, [graphNodes, setNodes, screenToFlowPosition]);

    const addResource = useCallback((node) => {
        const position = screenToFlowPosition({ x: left, y: top });
        const type = 'resource';
        Object.values<any>(node.parameters).forEach((p) => {
            p.value = p.default;
        });
        const newNode = ({ type, position, data: node });
        const newNodes = Graph.addNode(newNode, graphNodes);
        setNodes(newNodes);
        close();
    }, [graphNodes, setNodes, screenToFlowPosition]);

    return (
        <Card style={{ position: 'fixed', left, top, zIndex: 10 }}>
            <Search ref={searchRef} type="text" id="search" onChange={onInputChange} />
            <ResultList addStep={addStep} addResource={addResource} searchText={searchText} />
        </Card>
    );
}

function ResultList({ addStep, addResource, searchText }) {
    const [nodes, setNodes] = useState<any[]>([]);
    const [results, setResults] = useState<any[]>([]);
    const { token } = theme.useToken();

    useEffect(() => {
        const flattenNodes = (nodes) => {
            const flatten = (category, type) => {
                const arr: any[] = [];
                Object.values<any>(category).forEach((c) => {
                    if (c.children) {
                        arr.push(...flatten(c.children, type));
                    } else {
                        arr.push({ ...c, type });
                    }
                });
                return arr;
            };
    
            return [...flatten(nodes.steps, 'step'), ...flatten(nodes.resources, 'resource')];
        };

        const loadNodes = async () => {
            const nodes = await API.getNodes();
            setNodes(flattenNodes(nodes));
        };

        loadNodes();
    }, []);

    useEffect(() => {
        const filteredResults = nodes.filter((node) => {
            const category = node.category.toLowerCase();
            const name = node.name.toLowerCase();
            const longName = `${category}/${name}`;
            return longName.includes(searchText.toLowerCase());
        });

        setResults(filteredResults);
    }, [searchText, nodes]);

    const data = useMemo(() => results.map((result) => ({
        data: result,
        type: result.type })
    ), [results]);

    const onClick = useCallback((item) => {
        if (item.type === 'step') {
            addStep(item.data);
        }
        if (item.type === 'resource') {
            addResource(item.data);
        }
    }, [addStep, addResource]);

    return (
        <List
            style={{
                height: 400,
                overflow: 'auto',
                padding: '0 10px',
            }}
            itemLayout="horizontal"
            dataSource={data}
            renderItem={(item) => (
                <List.Item
                    onClick={() => onClick(item)}
                    style={{
                        cursor: 'pointer'
                    }}>
                    <span>
                        <Text style={{color: token.colorTextTertiary}}>{item.data.category}/</Text>
                        <Text>{item.data.name}</Text>
                    </span>
                </List.Item>
            )}
        />
    );
}
