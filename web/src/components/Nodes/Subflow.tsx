import React, { useMemo, useState, useCallback } from 'react';
import { useAPIMessageEffect } from '../../hooks/API';
import { useFilename } from '../../hooks/Filename';
import { getGlobalRunningFile } from '../../hooks/RunState';
import { Node } from './Node';
import type { Pin } from './Node';
import type { Parameter } from '../../utils';

type Output = {
    node: string,
    pin: string,
};

export function Subflow({ id, data, selected }) {
    const { name, isCollapsed } = data;
    const [recordCount, setRecordCount] = useState({});
    const filename = useFilename();

    const subscribedNodes = useMemo(() => {
        const subscribedNodes = new Set<string>();
        for (const outputs of Object.values(data.properties.stepOutputs)) {
            for (const output of outputs as Output[]) {
                subscribedNodes.add(output.node);
            }
        }
        return subscribedNodes;
    }, [data.properties.stepOutputs]);

    const updateStats = useCallback((msg: any) => {
        Object.entries<{queue_size: any}>(msg).forEach(([node, values]) => {
            if (filename === getGlobalRunningFile() && subscribedNodes.has(node)) {
                setRecordCount(prev => ({
                    ...prev,
                    [node]: values.queue_size
                }));
            }
        });
    }, [filename, subscribedNodes, setRecordCount]);

    useAPIMessageEffect('stats', updateStats);

    const [inputs, outputs, parameters] = useMemo(() => {
        const inputs: Pin[] = [];
        const outputs: Pin[] = [];
        const parameters: {[id: string]: Parameter} = {};
        if (!data.properties) {
            return [inputs, outputs, parameters];
        }

        for (const node of data.properties.nodes) {
            if (node.type === 'export') {
                if (node.data?.exportType === 'input') {
                    if (node.data.isResource) {
                        parameters[String(parameters.length)] = {
                            type: "resource",
                        };
                    } else {
                        inputs.push({
                            label: node.data.label,
                            isResource: false,
                            id: String(inputs.length)
                        });
                    }
                } else {
                    outputs.push({
                        label: node.data.label,
                        isResource: node.data.isResource,
                        id: String(outputs.length)
                    });
                }
            }
        }
        return [inputs, outputs, parameters];
    }, [data]);

    const outputsWithCounts = useMemo(() => {
        return outputs.map(output => {
            const count = data.properties.stepOutputs[output.id]?.reduce((acc, { node, pin }) => {
                return acc + (recordCount[node]?.[pin] || 0);
            }, 0) || 0;
            return {
                ...output,
                recordCount: count
            };
        });
    }, [outputs, recordCount]);

    return (
       <Node
            id={id}
            name={name}
            isRunnable={false}
            inputs={inputs}
            outputs={outputsWithCounts}
            parameters={parameters}
            selected={selected}
            errored={false}
            isCollapsed={isCollapsed}
       />
    );
}
