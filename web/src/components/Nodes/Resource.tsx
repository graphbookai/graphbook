import React, { useCallback, useState, useMemo } from 'react';
import { Handle, Position, useOnSelectionChange, useReactFlow } from 'reactflow';
import { Card, theme } from 'antd';
import { Widget } from './Widgets';
import { outputHandleStyle, nodeBorderStyle } from '../../styles';
import { Parameter } from '../../utils';
const { useToken } = theme;

const collapsedStyle = {
    maxWidth: '150px'
};

export function Resource({ id, data, selected }) {
    const { token } = useToken();
    const { getNode } = useReactFlow();
    const { name, parameters, isCollapsed } = data;
    const [parentSelected, setParentSelected] = useState(false);

    const borderStyle = useMemo(() => nodeBorderStyle(token, false, selected, parentSelected), [token, selected, parentSelected]);

    const onSelectionChange = useCallback(({ nodes }) => {
        const parentId = getNode(id)?.parentId;
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

    const firstParamValue = Object.values<Parameter>(parameters)[0]?.value;
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
                                    <Handle style={outputHandleStyle()} type="source" position={Position.Right} id="resource" />
                                </div>
                            </div>
                        </div> :
                        <div>
                            <span className="title">{name}</span>
                            {parameters &&
                                <div className='widgets'>
                                    {
                                        Object.entries<Parameter>(parameters).map(([parameterName, parameter], i) => {
                                            return (
                                                <div key={i} className="parameter">
                                                    <Widget id={id} type={parameter.type} name={parameterName} value={parameter.value}/>
                                                </div>
                                            );
                                        })
                                    }
                                </div>
                            }
                            <div className="handles" style={{marginBottom: '5px'}}>
                                <div className="inputs"></div>
                                <div className='outputs'>
                                    <div className="output">
                                        <Handle style={outputHandleStyle()} type="source" position={Position.Right} id="resource" />
                                    </div>
                                </div>
                            </div>
                        </div>
                }
            </Card>
        </div>
    );
}
