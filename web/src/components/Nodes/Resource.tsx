import React from 'react';
import { Node } from './NodeAPI';

export function Resource({ id, data, selected }) {
    const { name, parameters, isCollapsed } = data;

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
        />
    );
}
