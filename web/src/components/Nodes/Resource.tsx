import React, { useState, useMemo, useEffect } from 'react';
import { Node } from './Node';
import { useAPINodeMessageEffect, useLogSubscription } from '../../hooks/API';
import { useFilename } from '../../hooks/Filename';
import Icon, { FileTextOutlined } from '@ant-design/icons';
import { Braces } from '../../svg';
import { DataView, QuickViewEntry } from './tabs/DataView';
import { LogsView } from './tabs/LogsView';

export function Resource({ id, data, selected }) {
    const { name, parameters, isCollapsed } = data;
    const [quickViewData, setQuickViewData] = useState<QuickViewEntry>({});
    const [errored, setErrored] = useState<boolean>(false);
    const filename = useFilename();
    
    useAPINodeMessageEffect('view', id, filename, (msg) => {
        setQuickViewData(msg);
    });

    const logsData = useLogSubscription(filename, id);


    useEffect(() => {
        for (const log of logsData) {
            if (log.type === 'error') {
                setErrored(true);
                return;
            }
        }

        setErrored(false);
    }, [logsData]);

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
            errored={errored}
            isCollapsed={isCollapsed}
            tabs={tabs}
        />
    );
}
