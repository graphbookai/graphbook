import React, { useCallback, useRef, useEffect, useState } from 'react';
import { useReactFlow } from 'reactflow';
import { Input, Button } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { API } from '../api';
import { Graph } from '../graph';
import type { InputRef } from 'antd';
import './add-node.css';

export default function AddNode({ position, setNodeTo }) {
    const searchRef = useRef<InputRef>(null);
    const [searchText, setSearchText] = useState('');
    const { setNodes } = useReactFlow();

    useEffect(() => {
        if (searchRef.current) {
            searchRef.current.focus();
        }
    }, [searchRef]);

    const onInputChange = (e) => {
        setSearchText(e.target.value);
    };


    const onResultClick = useCallback(({ type, workflowType }) => {
        const addNode = (node) => {
            setNodes((nodes) => Graph.addNode(nodes, node));        
        };

        return () => {
            if (workflowType) {
                addNode({ type: 'step', position: setNodeTo, data: API.getNodeProperties(workflowType) });
            } else {
                addNode({ type, position: setNodeTo, data: {} });
            }
        }
    }, []);

    return (
        <div style={{ position: 'absolute', left: position.x, top: position.y }}>
            <div className='container'>
                <h2 className='title'>Add Node</h2>
                {/* <div className='quick-add'>
                    <Button icon={<PlusOutlined/>} onClick={onResultClick({ type:'codeResource' })}>
                        Code
                    </Button>
                </div> */}
                <Input ref={searchRef} type="text" id="search" onChange={onInputChange} />
                <ResultList onResultClick={onResultClick} searchText={searchText} />
            </div>
        </div>
    );
}

function ResultList({ onResultClick, searchText }) {
    const [nodes, setNodes] = useState<any>([]);
    const [results, setResults] = useState<any>([]);

    useEffect(() => {
        const loadNodes = async () => {
            const nodes = await API.getNodes();
            setNodes(nodes);
        };

        loadNodes();
    }, []);

    useEffect(() => {
        const resultNames = nodes.map((result) => result.name);
        searchText = searchText.toLowerCase();
        const filteredResultNames = resultNames.filter((result) => result.toLowerCase().includes(searchText));
        setResults(filteredResultNames);
    }, [searchText, nodes]);

    return (
        <div className='results'>
            {
                results.map((result, i) => {
                    return <div key={i} className='item' onClick={onResultClick({ workflowType: result })}>{result}</div>
                })
            }
        </div>
    );
}
