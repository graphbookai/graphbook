import './panel.css';

import { FileFilled, AppstoreOutlined } from '@ant-design/icons';
import { Tabs } from 'antd';

import Filesystem from './Filesystem';
import Extensions from './Extensions';

export default function LeftPanel({ onBeginEdit }) {
    const items = [
        {
            key: '1',
            label: 'Explorer',
            children: <Filesystem onBeginEdit={onBeginEdit}/>,
            icon: <FileFilled />,
        },
        {
            key: '2',
            label: 'Extensions',
            children: <Extensions />,
            icon: <AppstoreOutlined />,
        },
    ];
    
    return (
        <Tabs
            style={{margin: '10px'}}
            defaultActiveKey="1"
            items={items}
        />
    );
}