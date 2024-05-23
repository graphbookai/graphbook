import React, { useCallback, useRef, useEffect, useState } from 'react';
import { Button } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { API } from '../api';
import './add-node.css';

export default function AddNode({position, setNodeTo, addNode}) {
    const searchRef = useRef(null);
    const [searchText, setSearchText] = useState('');

    useEffect(() => {
        searchRef.current.focus();
    }, [searchRef]);

    const onInputChange = (e) => {
        setSearchText(e.target.value);
    };

    const onResultClick = useCallback(({type, workflowType}) => {
        return () => {
            if (workflowType) {
                addNode({ type: 'workflowStep', position: setNodeTo, data: API.getNodeProperties(workflowType)});
            } else {
                addNode({ type, position: setNodeTo, data: {}});
            }
        }
    });

    return (
        <div style={{position: 'absolute', left: position.x, top:position.y}}>
            <div className='container'>
                <h2 className='title'>Add Node</h2>
                <div className='quick-add'>
                    <Button icon={<PlusOutlined/>} onClick={onResultClick({ type:'codeResource' })}>
                        Code
                    </Button>
                </div>
                <input ref={searchRef} type="text" id="search" onChange={onInputChange}/>
                <ResultList onResultClick={onResultClick} searchText={searchText}/>
            </div>
        </div>
    );
}

function ResultList({onResultClick, searchText}) {
    const results = API.getNodeList();
    const resultNames = results.map((result) => result.name);
    searchText = searchText.toLowerCase();
    const filteredResultNames = resultNames.filter((result) => result.toLowerCase().includes(searchText));

    return (
        <div className='results'>
            {
                filteredResultNames.map((result, i) => {
                    return <div key={i} className='item' onClick={onResultClick( { workflowType: result} )}>{result}</div>
                })
            }
        </div>
    );
}
