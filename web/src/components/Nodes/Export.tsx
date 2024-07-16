import React, { useState, useMemo, useCallback } from 'react';
import { Card, Input, Flex, theme } from 'antd';
import { Handle, Position, useReactFlow } from 'reactflow';
import { Graph } from '../../graph';
import { nodeBorderStyle, inputHandleStyle, outputHandleStyle } from '../../styles';
const { useToken } = theme;

export function Export({ id, data, selected }) {
    const { token } = useToken();

    const { isEditing } = data;
    const [value, setValue] = useState(data.label);
    const { getNodes, setNodes } = useReactFlow();
    const onFinish = useCallback(() => {
        const newNodes = Graph.editNodeData(id, { label: value, isEditing: false }, getNodes());
        setNodes(newNodes);
    }, [id, value]);

    const ExportComponent = useMemo(() => {
        if (data.exportType === 'input') {
            return InputExport;
        }
        return OutputExport;
    }, [data.exportType]);

    const borderStyle = useMemo(() => nodeBorderStyle(token, false, selected, false), [token, selected]);

    return (
        <div style={borderStyle}>
            <Card className="workflow-node export">
                <ExportComponent isResource={data.isResource}>
                    {
                        isEditing ?
                            <Input
                                autoFocus
                                placeholder="pin"
                                value={value}
                                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setValue(e.target.value)}
                                onBlur={onFinish}
                                onPressEnter={onFinish}
                            /> :
                            <div className="title">{data.label}</div>
                    }
                </ExportComponent>
            </Card>
        </div>
    );
}

function InputExport({ children, isResource }) {
    return (
        <Flex vertical={false} justify='space-between'>
            {children}
            <div className="handles">
                <div className="outputs">
                    <Handle className={isResource ? "parameter" : "input"} style={inputHandleStyle()} type="source" position={Position.Right} id="in" />
                </div>
            </div>
        </Flex>
    )
}

function OutputExport({ children, isResource }) {
    return (
        <Flex vertical={false} justify='space-between'>
            <div className="handles">
                <div className="inputs">
                    <Handle className={isResource ? "parameter" : "input"} style={outputHandleStyle()} type="target" position={Position.Left} id="out" />
                </div>
            </div>
            {children}
        </Flex>
    )
}
