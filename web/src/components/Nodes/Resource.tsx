import React, { useCallback, useState, useMemo } from 'react';
import { Handle, Position, useOnSelectionChange, useReactFlow } from 'reactflow';
import { Card, theme } from 'antd';
import { Widget, isWidgetType } from './Widgets';
import { outputHandleStyle, inputHandleStyle, nodeBorderStyle } from '../../styles';
import { Parameter } from '../../utils';
import { usePluginResources } from '../../hooks/Plugins';
import { NodePlugin } from '../../plugins';
const { useToken } = theme;

const collapsedStyle = {
    maxWidth: '150px'
};

export function Resource({ id, data, selected, ...props }) {
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

    const pluginResources = usePluginResources();
    const customResource = useMemo(() => {
        const match = (pluginResource: NodePlugin) => {
            const { name, category } = pluginResource.for;
            if (name) {
                if (data.name === name) {
                    return pluginResource.component;
                }
            }
            if (category) {
                if (data.category === category) {
                    return pluginResource.component;
                }
            }
            return null;
        };

        for (const resource of pluginResources) {
            const component = match(resource);
            if (component) {
                return component;
            }
        }

        return null;
    }, [pluginResources]);

    const firstParamValue = Object.values<Parameter>(parameters)[0]?.value;
    const baseStyle = { backgroundColor: token.colorInfoBg };
    const style = isCollapsed ? { ...baseStyle, ...collapsedStyle } : baseStyle;
    return (
        <div style={borderStyle}>
            <Card className="workflow-node resource" style={style}>
                { customResource ? customResource({id, data, selected, ...props}) : isCollapsed ?
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
                        <div className="handles">
                            <div className="inputs">
                                {
                                    parameters &&
                                    Object.entries<Parameter>(parameters).map(([parameterName, parameter], i) => {
                                        if (!isWidgetType(parameter.type)) {
                                            return (
                                                <div key={i} className="input">
                                                    <Handle
                                                        className="parameter"
                                                        style={inputHandleStyle()}
                                                        type="target"
                                                        position={Position.Left}
                                                        id={parameterName}
                                                    />
                                                    <span className="label">{parameterName}</span>
                                                </div>
                                            );
                                        }
                                    })
                                }
                            </div>
                            <div className='outputs'>
                                <div className="output">
                                    <span className="label">out</span>
                                    <Handle style={outputHandleStyle()} type="source" position={Position.Right} id="resource" />
                                </div>
                            </div>
                        </div>
                        <div className='widgets'>
                            {
                                parameters && !data.isCollapsed &&
                                Object.entries<Parameter>(parameters).map(([parameterName, parameter], i) => {
                                    if (isWidgetType(parameter.type)) {
                                        return (
                                            <div key={i} className="parameter">
                                                <Widget id={id} type={parameter.type} name={parameterName} value={parameter.value}/>
                                            </div>
                                        );
                                    }
                                    return null;
                                }).filter(x => x)
                            }
                        </div>
                    </div>
                }
            </Card>
        </div>
    );
}
