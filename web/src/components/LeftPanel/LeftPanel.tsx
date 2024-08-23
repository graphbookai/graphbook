import './panel.css';

import React from 'react';
import { FileFilled, AppstoreOutlined } from '@ant-design/icons';
import { Tabs } from 'antd';

import Filesystem from './Filesystem';
import Extensions from './Extensions';

export default function LeftPanel({ setWorkflow, onBeginEdit }) {
    const items = [
        {
            key: '1',
            label: 'Explorer',
            children: <Filesystem setWorkflow={setWorkflow} onBeginEdit={onBeginEdit}/>,
            icon: <FileFilled />,
        },
        // {
        //     key: '2',
        //     label: 'Extensions',
        //     children: <Extensions />,
        //     icon: <AppstoreOutlined />,
        // },
    ];
    
    return (
        <Tabs
            style={{margin: '10px', display: 'flex', flex: 1, height: '100%', overflow: 'hidden'}}
            defaultActiveKey="1"
            items={items}
        />
    );
}
