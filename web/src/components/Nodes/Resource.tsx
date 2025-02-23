import React, { useState, useMemo } from 'react';
import { Node } from './Node';
import { useAPINodeMessageEffect } from '../../hooks/API';
import { useFilename } from '../../hooks/Filename';
import Icon from '@ant-design/icons';
import { Braces } from '../../svg';
import { DataView, QuickViewEntry } from './tabs/DataView';

export function Resource({ id, data, selected }) {
    const { name, parameters, isCollapsed } = data;
    const [quickViewData, setQuickViewData] = useState<QuickViewEntry>({});
    const filename = useFilename();
    
    useAPINodeMessageEffect('view', id, filename, (msg) => {
        setQuickViewData(msg);
    });

    const tabs = useMemo(() => {
        const t = [{
            label: 'Data',
            children: <DataView data={quickViewData} />,
            icon: <Icon component={Braces} />
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
