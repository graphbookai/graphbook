import React, { useState, useMemo } from 'react';
import { Node } from './Node';
import { useAPINodeMessageEffect } from '../../hooks/API';
import { useFilename } from '../../hooks/Filename';
import Icon, { FileTextOutlined } from '@ant-design/icons';
import { Braces } from '../../svg';
import { DataView, QuickViewEntry } from './tabs/DataView';
import { getMergedLogs } from '../../utils';
import { LogsView } from './tabs/LogsView';
import type { LogEntry } from '../../utils';

export function Resource({ id, data, selected }) {
    const { name, parameters, isCollapsed } = data;
    const [quickViewData, setQuickViewData] = useState<QuickViewEntry>({});
    const [logsData, setLogsData] = useState<LogEntry[]>([]);
    const [errored, setErrored] = useState<boolean>(false);
    const filename = useFilename();
    
    useAPINodeMessageEffect('view', id, filename, (msg) => {
        setQuickViewData(msg);
    });

    useAPINodeMessageEffect('logs', id, filename, (newEntries) => {
        setLogsData(prev => getMergedLogs(prev, newEntries));
    });

    const tabs = useMemo(() => {
        const t = [{
            label: 'Data',
            children: <DataView data={quickViewData} />,
            icon: <Icon component={Braces} />
        }, {
            label: logsData.length === 0 ? 'Logs' : `Logs (${logsData.length})`,
            children: <LogsView data={logsData} />,
            icon: <FileTextOutlined />
        }];
        return t;
    }, [quickViewData]);

    return (
        <Node
            id={id}
            isRunnable={false}
            style={{ borderColor: '#e6a857' }}
            name={name}
            inputs={[]}
            parameters={parameters}
            outputs={[{id: "resource", label: "", isResource: true}]}
            selected={selected}
            errored={false}
            isCollapsed={isCollapsed}
            tabs={tabs}
        />
    );
}
