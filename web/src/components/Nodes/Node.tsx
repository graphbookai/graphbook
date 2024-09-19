import React, { CSSProperties, useCallback, useEffect, useMemo, useState } from 'react';
import { Handle, Position, useNodes, useEdges, useReactFlow, useOnSelectionChange } from 'reactflow';
import { Card, Collapse, Badge, Flex, Button, Image, Tabs, theme, Space } from 'antd';
import { SearchOutlined, FileTextOutlined, CaretRightOutlined, FileImageOutlined, CodeOutlined } from '@ant-design/icons';
import { Widget, isWidgetType } from './widgets/Widgets';
import { Graph } from '../../graph';
import { useRunState } from '../../hooks/RunState';
import { useAPI, useAPINodeMessage } from '../../hooks/API';
import { useFilename } from '../../hooks/Filename';
import { recordCountBadgeStyle, nodeBorderStyle, inputHandleStyle, outputHandleStyle } from '../../styles';
import { getMergedLogs, getMediaPath } from '../../utils';
import { useNotification } from '../../hooks/Notification';
import { useSettings } from '../../hooks/Settings';
import { SerializationErrorMessages } from '../Errors';
import { Prompt } from './widgets/Prompts';
import ReactJson from '@microlink/react-json-view';
import type { LogEntry, Parameter, ImageRef } from '../../utils';

const { Panel } = Collapse;
const { useToken } = theme;

type QuickViewEntry = {
    [key: string]: any;
};

export function WorkflowStep({ id, data, selected }) {
    const { name, parameters, inputs, outputs } = data;
    const [quickViewData, setQuickViewData] = useState<QuickViewEntry>({});
    const [logsData, setLogsData] = useState<LogEntry[]>([]);
    const [recordCount, setRecordCount] = useState({});
    const [errored, setErrored] = useState(false);
    const [parentSelected, setParentSelected] = useState(false);
    const [runState, runStateShouldChange] = useRunState();
    const nodes = useNodes();
    const edges = useEdges();
    const { token } = useToken();
    const { getNode } = useReactFlow();
    const notification = useNotification();
    const API = useAPI();
    const filename = useFilename();

    useAPINodeMessage('stats', id, filename, (msg) => {
        setRecordCount(msg.queue_size || {});
    });
    useAPINodeMessage('view', id, filename, (msg) => {
        setQuickViewData(msg);
    });
    useAPINodeMessage('logs', id, filename, useCallback((newEntries) => {
        setLogsData(prev => getMergedLogs(prev, newEntries));
    }, [setLogsData]));

    useEffect(() => {
        for (const log of logsData) {
            if (log.type === 'error') {
                setErrored(true);
                return;
            }
        }

        setErrored(false);
    }, [logsData]);

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
    const badgeIndicatorStyle = useMemo(() => recordCountBadgeStyle(token), [token]);

    return (
        <div style={borderStyle}>
            <Card className="workflow-node">
                <Flex gap="small" justify='space-between' className='title'>
                    <div>{name}</div>
                    <Button shape="circle" icon={<CaretRightOutlined />} size={"small"} onClick={run} disabled={runState !== 'stopped' || !API} />
                </Flex>
                <div className="handles">
                    <div className="inputs">
                        {
                            inputs.map((input, i) => {
                                return (
                                    <div key={i} className="input">
                                        <Handle style={inputHandleStyle()} type="target" position={Position.Left} id="in" />
                                        <span className="label">{input}</span>
                                    </div>
                                );
                            })
                        }
                        {
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
                        {
                            outputs.map((output, i) => {
                                return (
                                    <div key={i} className="output">
                                        <Badge size="small" styles={{ indicator: badgeIndicatorStyle }} count={recordCount[output] || 0} overflowCount={Infinity} />
                                        <span className="label">{output}</span>
                                        <Handle style={outputHandleStyle()} type="source" position={Position.Right} id={output} />
                                    </div>
                                );
                            })
                        }
                    </div>
                </div>
                <div className='widgets'>
                    {
                        !data.isCollapsed &&
                        Object.entries<Parameter>(parameters).map(([parameterName, parameter], i) => {
                            if (isWidgetType(parameter.type)) {
                                return (
                                    <div style={{ marginBottom: '2px' }} key={i} className="parameter">
                                        <Widget id={id} type={parameter.type} name={parameterName} value={parameter.value} />
                                    </div>
                                );
                            }
                            return null;
                        }).filter(x => x)
                    }
                </div>
                <div className="widgets">
                    <Prompt nodeId={id}/>
                </div>
                {!data.isCollapsed && <Monitor quickViewData={quickViewData} logsData={logsData} />}
            </Card>
        </div>
    );
}

function Monitor({ quickViewData, logsData }) {
    return (
        <Collapse className='quickview' defaultActiveKey={[]} bordered={false} expandIcon={({ header }) => {
            const h = header as String;
            if (h.startsWith('Quickview')) {
                return <SearchOutlined />;
            }
            if (h.startsWith('Logs')) {
                return <FileTextOutlined />;
            }
            return null;
        }}>
            <Panel header="Quickview" key="1">
                {
                    quickViewData ?
                        <QuickviewCollapse data={quickViewData} /> :
                        '(No outputs yet)'
                }
            </Panel>
            <Panel header={"Logs" + (logsData.length > 0 ? ` (${logsData.length})` : '')} key="2">
                {
                    logsData.length == 0 ?
                        <p className='content'>(No logs yet) </p> :
                        (
                            <div style={{ maxHeight: '200px', overflow: 'auto' }}>
                                {
                                    logsData.map((log, i) => {
                                        const { msg } = log;
                                        return (
                                            <p style={{ fontFamily: 'monospace' }} key={i}>
                                                {JSON.stringify(msg)}
                                            </p>
                                        );
                                    })
                                }

                            </div>
                        )
                }
            </Panel>
        </Collapse>
    );
}

function QuickviewCollapse({ data }) {
    const [settings, _] = useSettings();
    const globalTheme = theme.useToken().theme;

    const tabItems = useCallback((noteData) => {
        let data: any = [];
        if (settings.quickviewShowNotes) {
            data.push({
                key: '0',
                label: 'Note',
                icon: <CodeOutlined />,
                children: (
                    <ReactJson
                        style={{ maxHeight: '200px', overflow: 'auto', fontSize: '0.6em' }}
                        theme={globalTheme.id === 0 ? "rjv-default" : "monokai"}
                        name={false}
                        displayDataTypes={false}
                        indentWidth={2}
                        src={noteData}
                    />
                ),
            });
        }
        if (settings.quickviewShowImages) {
            data.push({
                key: '1',
                label: 'Images',
                icon: <FileImageOutlined />,
                children: (
                    <EntryImages
                        style={{ maxHeight: '200px', overflow: 'auto' }}
                        entry={noteData}
                    />
                ),
            });
        }
        return data;
    }, [settings]);

    return (
        <Collapse className='quickview' defaultActiveKey={[]} bordered={false}>
            {
                Object.entries<QuickViewEntry>(data).map(([key, value], i) => {
                    return (
                        <Panel className='content nowheel' header={key} key={i} style={{ overflow: 'auto' }}>
                            <Tabs
                                tabBarStyle={{ fontSize: '2px' }}
                                defaultActiveKey="0"
                                items={tabItems(value)}
                            />
                        </Panel>
                    );
                })
            }
        </Collapse>
    );
}

function EntryImages({ entry, style }: { entry: QuickViewEntry, style: CSSProperties | undefined }) {
    const [settings, _] = useSettings();

    const imageEntries = useMemo(() => {
        let entries: { [key: string]: ImageRef[] } = {};
        Object.entries<QuickViewEntry>(entry).forEach(([key, item]) => {
            let imageItems: any = [];
            if (Array.isArray(item)) {
                imageItems = item.filter(item => item.type?.slice(0, 5) === 'image');
            } else {
                if (item.type?.slice(0, 5) === 'image') {
                    imageItems.push(item);
                }
            }
            if (imageItems.length > 0) {
                entries[key] = imageItems;
            }
        });
        return entries;
    }, [entry]);

    return (
        <Flex style={style}>
            {
                Object.entries<ImageRef[]>(imageEntries).map(([key, images]) => {
                    return (
                        <Space key={key} direction="vertical" align='center'>
                            <div>{key}</div>
                            <Flex vertical>
                                {
                                    images.map((image, i) => (
                                        <Image key={i} src={getMediaPath(settings, image)} height={settings.quickviewImageHeight} />
                                    ))
                                }
                            </Flex>
                        </Space>

                    );
                })
            }
        </Flex>
    );
}
