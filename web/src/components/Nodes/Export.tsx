import React, { useState, useMemo, useCallback } from 'react';
import { Card, Input, Flex, theme } from 'antd';
import { Handle, Position, useReactFlow } from 'reactflow';
import { Graph } from '../../graph';
const { useToken } = theme;

const borderStyleFn = (token, selected) => {
    const baseStyle = {
        padding: '1px',
        borderRadius: token.borderRadius,
        transform: 'translate(-2px, -2px)'
    };

    const selectedStyle = {
        ...baseStyle,
        border: `1px dashed ${token.colorInfoActive}`
    };

    if (selected) {
        return selectedStyle;
    }
};

export function Export({ id, data, selected }) {
    const { token } = useToken();
    const borderStyle = useMemo(() => {
        const selectedStyle = {
            padding: '1px',
            borderRadius: token.borderRadius,
            border: `1px dashed ${token.colorInfoActive}`,
            transform: 'translate(-2px, -2px)'
        };

        if (selected) {
            return selectedStyle;
        }

        return {};

    }, [token, selected]);

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

const handleStyle = {
    borderRadius: '50%',
    position: 'absolute',
    top: '50%',
    transform: 'translate(0,-50%)',
};

const inputHandleStyle = {
    ...handleStyle,
    right: 5,
    left: 'auto',
};

const outputHandleStyle = {
    ...handleStyle,
    left: 5,
    right: 'auto',
};

function InputExport({ children, isResource }) {
    return (
        <Flex vertical={false} justify='space-between'>
            {children}
            <div className="handles">
                <div className="outputs">
                    <div style={{ width: 10 }}></div>
                    <Handle className={isResource ? "parameter" : "input"} style={inputHandleStyle} type="source" position={Position.Right} id="in" />
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
                    <div style={{ width: 10 }}></div>
                    <Handle className={isResource ? "parameter" : "input"} style={outputHandleStyle} type="target" position={Position.Left} id="out" />
                </div>
            </div>
            {children}
        </Flex>
    )
}

