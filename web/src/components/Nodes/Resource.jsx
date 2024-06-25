import { useCallback, useState, useMemo } from 'react';
import { Handle, Position, useOnSelectionChange, useReactFlow } from 'reactflow';
import { Card, theme } from 'antd';
import { Widget } from './Widgets';
const { useToken } = theme;
import './node.css';

const handleStyle = {
    borderRadius: '50%',
    position: 'relative',
    top: '0%',
    right: 0,
    left: 0,
    transform: 'translate(0,0)',
};

const absoluteHandleStyle = {
    position: 'absolute',
    top: '50%',
    right: 10,
    left: 'auto',
    transform: 'translate(0, -50%)'
}

const parameterHandleStyle = {
    ...handleStyle,
    borderRadius: '50%',
    marginLeft: '5px'
};

const collapsedStyle = {
    maxWidth: '150px'
};

export function Resource({ id, data, selected }) {
    const { token } = useToken();
    const { getNode } = useReactFlow();
    const { name, parameters, isCollapsed } = data;
    const [parentSelected, setParentSelected] = useState(false);

    const borderStyle = useMemo(() => {
        const baseStyle = {
            padding: '1px',
            borderRadius: token.borderRadius,
            transform: 'translate(-2px, -2px)'
        };

        const selectedStyle = {
            ...baseStyle,
            border: `1px dashed ${token.colorInfoActive}`
        };

        const parentSelectedStyle = {
            ...baseStyle,
            border: `1px dashed ${token.colorInfoBorder}`
        };

        if (selected) {
            return selectedStyle;
        }

        if (parentSelected) {
            return parentSelectedStyle;
        }

    }, [token, selected, parentSelected]);

    const onSelectionChange = useCallback(({ nodes }) => {
        const parentId = getNode(id).parentId;
        if (!parentId) {
            return;
        }
        for (const n of nodes) {
            if (parentId === n.id && n.selected) {
                setParentSelected(true);
                return;
            }
        }
        setParentSelected(false);
    }, [id]);

    useOnSelectionChange({
        onChange: onSelectionChange
    });

    const firstParamValue = Object.values(parameters)[0].value;
    const baseStyle = { backgroundColor: token.colorInfoBg };
    const style = isCollapsed ? { ...baseStyle, ...collapsedStyle } : baseStyle;
    return (
        <div style={borderStyle}>
            <Card className="workflow-node resource" style={style}>
                {
                    isCollapsed ?
                        <div className="collapsed">
                            <div className="title type">{name}</div>
                            <div className="title value">{firstParamValue}</div>
                            <div className="handles">
                                <div className="outputs">
                                    <Handle style={{ ...parameterHandleStyle, ...absoluteHandleStyle }} type="source" position={Position.Right} id="resource" />
                                </div>
                            </div>
                        </div> :
                        <div>
                            <span className="title">{name}</span>
                            {parameters &&
                                <div className='widgets'>
                                    {
                                        Object.entries(parameters).map(([parameterName, parameter], i) => {
                                            return (
                                                <div key={i} className="parameter">
                                                    <Widget id={id} name={parameterName} {...parameter} />
                                                </div>
                                            );
                                        })
                                    }
                                </div>
                            }
                            <div className="handles">
                                <div className="inputs"></div>
                                <div className='outputs'>
                                    <div className="output">
                                        <Handle style={parameterHandleStyle} type="source" position={Position.Right} id="resource" />
                                    </div>
                                </div>
                            </div>
                        </div>
                }
            </Card>
        </div>
    );
}
