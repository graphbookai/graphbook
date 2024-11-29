import React, { CSSProperties, useCallback, useEffect, useMemo, useState } from 'react';
import { Handle, Position, useNodes, useEdges, useReactFlow, useOnSelectionChange } from 'reactflow';
import { Card, Collapse, Badge, Flex, Button, Image, Tabs, theme, Space, Empty } from 'antd';
import { SearchOutlined, FileTextOutlined, CaretRightOutlined, FileImageOutlined, CodeOutlined } from '@ant-design/icons';
import { Widget, isWidgetType } from './widgets/Widgets';
import { Graph } from '../../graph';
import { useRunState } from '../../hooks/RunState';
import { useAPI, useAPINodeMessage } from '../../hooks/API';
import { useFilename } from '../../hooks/Filename';
import { nodeBorderStyle } from '../../styles';
import { getMergedLogs, getMediaPath } from '../../utils';
import { useNotification } from '../../hooks/Notification';
import { useSettings } from '../../hooks/Settings';
import { SerializationErrorMessages } from '../Errors';
import { Prompt } from './widgets/Prompts';
import { InputHandle, OutputHandle } from './Handle';
import ReactJson from '@microlink/react-json-view';
import type { LogEntry, Parameter, ImageRef } from '../../utils';

const { Panel } = Collapse;
const { useToken } = theme;

type QuickViewEntry = {
    [key: string]: any;
};

type Pin = {
    id: string;
    label: string;
    isResource?: boolean;
}

export type NodeProps = {
    id: string;
    style?: React.CSSProperties,
    name: string;
    inputs: Pin[];
    parameters: any;
    outputs: Pin[];
    selected: boolean;
    errored: boolean;
    isCollapsed: boolean;
    tabs?: any;
    isRunnable?: boolean;
}

export function Node({ id, style, name, inputs, parameters, outputs, selected, errored, isCollapsed, tabs, ...props }: NodeProps) {
    const [recordCount, setRecordCount] = useState({});
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
    tabs = tabs || [];
    const tabList = useMemo(() => 
        [{
            key: 'Params',
            label: 'Params'
        }, ...tabs.map(tab => ({...tab, key: tab.label, children: undefined}))], [tabs]);

    useAPINodeMessage('stats', id, filename, (msg) => {
        setRecordCount(msg.queue_size || {});
    });

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
                    <div>{name}</div>
                    {
                        isRunnable && 
                        <Button shape="circle" icon={<CaretRightOutlined />} size={"small"} onClick={run} disabled={runState !== 'stopped' || !API} />
                    }
                </Flex>
                { 
                    !isCollapsed && tabs.length > 0 &&
                    <Tabs items={tabList} defaultActiveKey={tabs[tabShown]?.label || 'Params'} onTabClick={onTabClick} />
                }
                <div style={{position: 'relative'}}>
                    <ContentDefault
                        id={id}
                        inputs={inputs}
                        parameters={parameters}
                        outputs={outputs}
                        isCollapsed={isCollapsed}
                        recordCount={recordCount}
                        shown={tabShown === -1}
                    />
                    <ContentOverlay>
                        { !isCollapsed && tabs[tabShown]?.children }
                    </ContentOverlay>
                </div>
            </Card>
        </div>
    );
}

export type EmptyTabProps = {
    description?: string;
};

export function EmptyTab({ description }: EmptyTabProps) {
    return (
        <Empty
            style={{ fontSize: 8 }}
            imageStyle={{ height: 40 }}
            description={description}
        />
    );
}

function ContentDefault({ id, inputs, parameters, outputs, isCollapsed, recordCount, shown }) {
    const collapsed = useMemo(() => !shown || isCollapsed, [shown, isCollapsed]);
    return (
        <div>
            <div className="handles">
                <div className="inputs">
                    {
                        inputs.length > 0 &&
                        <InputHandle collapsed={collapsed} id="in" name="in" />
                    }
                    {
                        Object.entries<Parameter>(parameters).map(([parameterName, parameter], i) => {
                            if (!isWidgetType(parameter.type)) {
                                const { required, description } = parameter;
                                const tooltip = required ? `(required) ${description}` : description;
                                return (
                                    <InputHandle collapsed={collapsed} key={parameterName} id={parameterName} name={parameterName} isResource={true} tooltip={tooltip} />
                                );
                            }
                        })
                    }
                </div>
                <div className='outputs'>
                    {
                        outputs.map(output => (
                            <OutputHandle
                                key={output.id}
                                collapsed={collapsed}
                                id={output.id}
                                name={output.label}
                                count={recordCount[output.id]}
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
            {/* <div className="widgets">
                <Prompt nodeId={id} />
            </div> */}
        </div>
    )
}

function ContentOverlay({ children }) {
    if (!children) {
        return null;
    }

    const overlayStyle = {
        background: 'white',
        width: '100%',
        maxWidth: '200px',
        maxHeight: '200px',
        zIndex: 5,
        overflow: 'auto'
    };

    return (
        <div style={overlayStyle}>
            { children }
        </div>
    );
}
