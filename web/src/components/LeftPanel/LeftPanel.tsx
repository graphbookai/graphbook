import './panel.css';

import React, { useMemo } from 'react';
import { FileFilled, AppstoreOutlined } from '@ant-design/icons';
import { Tabs } from 'antd';
import Filesystem from './Filesystem';
import { usePluginPanels } from '../../hooks/Plugins';
import ErrorBoundary from '../ErrorBoundary';

export default function LeftPanel({ setWorkflow, setExecution, onBeginEdit }) {
    const panels = usePluginPanels();
    const items = useMemo(() => {
        const pluginPanels = panels.map((p, i) => ({ ...p, key: (i + 1).toString(), icon: p.icon || <AppstoreOutlined /> }));
        return [
            {
                key: '0',
                label: 'Explorer',
                children: (
                    <ErrorBoundary>
                        <Filesystem setWorkflow={setWorkflow} setExecution={setExecution} onBeginEdit={onBeginEdit} />
                    </ErrorBoundary>
                ),
                icon: <FileFilled />,
            },
            ...pluginPanels
        ]
    }, [panels]);

    return (
        <Tabs
            style={{ margin: '10px', display: 'flex', flex: 1, height: '100%', overflow: 'hidden' }}
            defaultActiveKey="1"
            items={items}
        />
    );
}
