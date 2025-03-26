import React, { useCallback, useMemo, useState, useEffect } from 'react';
import { useNodes, useEdges, useReactFlow, useOnSelectionChange } from 'reactflow';
import { Card, Flex, Button, Tabs, theme, Empty } from 'antd';
import { ControlOutlined, CaretRightOutlined } from '@ant-design/icons';
import { Widget, isWidgetType } from './widgets/Widgets';
import { Graph, getNodeParams } from '../../graph';
import { useRunState } from '../../hooks/RunState';
import { useAPI } from '../../hooks/API';
import { useFilename } from '../../hooks/Filename';
import { nodeBorderStyle } from '../../styles';
import { useNotification } from '../../hooks/Notification';
import { SerializationErrorMessages } from '../Errors';
import { InputHandle, OutputHandle } from './Handle';
import type { Parameter } from '../../utils';
import { useSettings } from '../../hooks/Settings';

const { useToken } = theme;

export type Pin = {
    id: string;
    label: string;
    isResource?: boolean;
    recordCount?: number;
}

export type NodeProps = {
    id: string;
    style?: React.CSSProperties,
    name?: string;
    parameters?: { [key: string]: Parameter };
    inputs: Pin[];
    outputs: Pin[];
    selected: boolean;
    errored: boolean;
    isCollapsed: boolean;
    tabs?: any;
    isRunnable?: boolean;
    defaultTab?: string;
}

export function Node({ id, style, name, inputs, parameters, outputs, selected, errored, isCollapsed, tabs, ...props }: NodeProps) {
    const [parentSelected, setParentSelected] = useState(false);
    const [runState, runStateShouldChange] = useRunState();
    const nodes = useNodes();
    const edges = useEdges();
    const { token } = useToken();
    const { getNode } = useReactFlow();
    const notification = useNotification();
    const API = useAPI();
    const filename = useFilename();
    const [tabShown, setTabShown] = useState(-1);
    const isRunnable = props.isRunnable === undefined ? true : false;
    const [settings, _] = useSettings();
    tabs = tabs || [];
    const tabList = useMemo(() => {
        const data = [{
            key: 'Params',
            label: 'Params',
            icon: <ControlOutlined />,
        }, ...tabs.map(tab => ({
            key: tab.label,
            label: tab.label,
            icon: tab.icon,
            children: undefined
        }))];
        const showIcon = settings.nodeTabsDisplay === "ICONS" || settings.nodeTabsDisplay === "BOTH";
        const showLabel = settings.nodeTabsDisplay === "NAMES" || settings.nodeTabsDisplay === "BOTH";
        return data.map(d => ({
            ...d,
            icon: showIcon ? d.icon : undefined,
            label: showLabel ? d.label : undefined,
        }));
    }, [tabs, settings]);

    useEffect(() => {
        if (props.defaultTab) {
            const tabIndex = tabs.findIndex(tab => props.defaultTab === tab.label);
            if (tabIndex !== -1) {
                setTabShown(tabIndex);
            }
        }
    }, [props.defaultTab])

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

    const run = useCallback(async () => {
        if (!API) {
            return;
        }
        if (filename.endsWith('.json')) {
            const [[graph, resources], errors] = await Graph.serializeForAPI(nodes, edges);
            if (errors.length > 0) {
                notification.error({
                    key: 'invalid-graph',
                    message: 'Invalid Graph',
                    description: <SerializationErrorMessages errors={errors} />,
                    duration: 3,
                })
                return;
            }
            API.run(graph, resources, id, filename);
        } else {
            const params = getNodeParams(nodes);
            API.pyRun(filename, id, params);
        }
        runStateShouldChange();
    }, [nodes, edges, API, notification, filename]);

    const borderStyle = useMemo(() => nodeBorderStyle(token, errored, selected, parentSelected), [token, errored, selected, parentSelected]);
    const onTabClick = useCallback((key) => {
        const tabIndex = tabs.findIndex(tab => key === tab.label);
        if (tabIndex === -1) {
            setTabShown(-1);
            return;
        }

        setTabShown(tabIndex);
    }, [tabs]);

    return (
        <div style={borderStyle}>
            <Card className="workflow-node" style={style}>
                <Flex gap="small" justify='space-between' className='title'>
                    {
                        name &&
                        <div>{name}</div>
                    }
                    {
                        isRunnable &&
                        <Button shape="circle" icon={<CaretRightOutlined />} size={"small"} onClick={run} disabled={runState !== 'finished' || !API} />
                    }
                </Flex>
                {
                    !isCollapsed && tabs.length > 0 &&
                    <Tabs items={tabList} defaultActiveKey={props.defaultTab || 'Params'} onTabClick={onTabClick} />
                }
                <div className="nowheel" style={{ position: 'relative' }}>
                    <ContentDefault
                        id={id}
                        inputs={inputs}
                        parameters={parameters}
                        outputs={outputs}
                        isCollapsed={isCollapsed}
                        shown={tabShown === -1}
                    />
                    <ContentOverlay>
                        {!isCollapsed && tabs[tabShown]?.children}
                    </ContentOverlay>
                </div>
            </Card>
        </div>
    );
}

function ContentDefault({ id, inputs, parameters, outputs, isCollapsed, shown }) {
    const collapsed = useMemo(() => !shown || isCollapsed, [shown, isCollapsed]);
    const [inputEntries, outputEntries] = useMemo(() => {
        const fn = (data) => {
            return data.map(d => {
                if (typeof (d) === 'string') {
                    return { id: d, label: d };
                }
                return d;
            });
        };
        return [fn(inputs), fn(outputs)];
    }, [inputs, outputs]);
    return (
        <div>
            <div className="handles">
                <div className="inputs">
                    {
                        inputEntries.map(input => (
                            <InputHandle
                                key={input.id}
                                collapsed={collapsed}
                                id={input.id}
                                name={input.label}
                            />
                        ))
                    }
                    {
                        parameters &&
                        Object.entries<Parameter>(parameters).map(([parameterName, parameter], i) => {
                            if (!isWidgetType(parameter.type)) {
                                const { required, description } = parameter;
                                const tooltip = required ? `(required) ${description}` : description;
                                return (
                                    <InputHandle
                                        key={parameterName}
                                        id={parameterName}
                                        collapsed={collapsed}
                                        name={parameterName}
                                        isResource={true}
                                        tooltip={tooltip}
                                    />
                                );
                            }
                        })
                    }
                </div>
                <div className='outputs'>
                    {
                        outputEntries.map(output => (
                            <OutputHandle
                                key={output.id}
                                collapsed={collapsed}
                                id={output.id}
                                name={output.label}
                                count={output.recordCount}
                                isResource={output.isResource}
                            />
                        ))
                    }
                </div>
            </div>
            {
                shown &&
                <div className='widgets'>
                    {
                        parameters &&
                        !isCollapsed &&
                        Object.entries<Parameter>(parameters).map(([parameterName, parameter], i) => {
                            if (isWidgetType(parameter.type)) {
                                return (
                                    <div style={{ marginBottom: '2px' }} key={i} className="parameter">
                                        <Widget {...parameter} id={id} type={parameter.type} name={parameterName} value={parameter.value} />
                                    </div>
                                );
                            }
                            return null;
                        }).filter(x => x)
                    }
                </div>
            }
        </div>
    )
}

function ContentOverlay({ children }) {
    if (!children) {
        return null;
    }

    const overlayStyle = {
        width: '100%',
        maxWidth: '400px',
        maxHeight: '400px',
        zIndex: 1,
        overflow: 'auto'
    };

    return (
        <div style={overlayStyle}>
            {children}
        </div>
    );
}
