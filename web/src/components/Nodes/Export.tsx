import React, { useState, useMemo, useCallback } from 'react';
import { Card, Input } from 'antd';
import { useReactFlow } from 'reactflow';
import { Graph } from '../../graph';
import { Node } from './Node';

export function Export({ id, data, selected }) {
    const outputs = useMemo(() => {
        if (data.exportType === 'input') {
            return [{ id: "in", label: data.label, isResource: data.isResource }];
        }

        return [];
    }, [data.label, data.exportType, data.isResource]);

    const inputs = useMemo(() => {
        if (data.exportType === 'output' && !data.isResource) {
            return [{ id: "out", label: data.label }]
        }
        return [];
    }, [data.label, data.exportType, data.isResource]);

    const parameters = useMemo(() => {
        if (data.exportType === 'output' && data.isResource) {
            return {
                [data.label]: {
                    type: "resource"
                }
            }
        }
        return {};
    }, [data.label, data.exportType, data.isResource]);

    const { isEditing } = data;
    const [value, setValue] = useState(data.label);
    const { getNodes, setNodes } = useReactFlow();
    const onFinish = useCallback(() => {
        const newNodes = Graph.editNodeData(id, { label: value, isEditing: false }, getNodes());
        setNodes(newNodes);
    }, [id, value]);

    if (isEditing) {
        return (
            <Card>
                <Input
                    styles={{
                        input: {
                            fontSize: '.6em',
                            padding: 0,
                        }
                    }}
                    autoFocus
                    placeholder="pin"
                    value={value}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setValue(e.target.value)}
                    onBlur={onFinish}
                    onPressEnter={onFinish}
                />
            </Card>
        );
    }

    return (
        <Node
            id={id}
            isRunnable={false}
            inputs={inputs}
            outputs={outputs}
            parameters={parameters}
            selected={selected}
            errored={false}
            isCollapsed={false}
        />
    );
}
