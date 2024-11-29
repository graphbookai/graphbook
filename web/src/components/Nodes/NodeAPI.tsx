import React, { CSSProperties, useCallback, useEffect, useMemo, useState } from 'react';
import { Handle, Position, useNodes, useEdges, useReactFlow, useOnSelectionChange } from 'reactflow';
import { Card, Collapse, Badge, Flex, Button, Image, Tabs, theme, Space } from 'antd';
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

export function Node({ id, name, requiresInput, parameters, outputs, selected, errored, isCollapsed, tabs }) {
    // const { name, parameters, inputs, outputs } = data;
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
    const tabList = useMemo(() => 
        [{
            key: 'Params',
            label: 'Params'
        }, ...tabs.map((tab, i) => ({...tab, key: tab.label, children: undefined}))], [tabs]);

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
            <Card className="workflow-node">
                <Flex gap="small" justify='space-between' className='title'>
                    <div>{name}</div>
                    <Button shape="circle" icon={<CaretRightOutlined />} size={"small"} onClick={run} disabled={runState !== 'stopped' || !API} />
                </Flex>
                <Tabs items={tabList} onTabClick={onTabClick} />
                <div style={{position: 'relative'}}>
                    <div className="handles">
                        <div className="inputs">
                            {
                                requiresInput &&
                                <InputHandle id="in" name="in" />
                            }
                            {
                                Object.entries<Parameter>(parameters).map(([parameterName, parameter], i) => {
                                    if (!isWidgetType(parameter.type)) {
                                        const { required, description } = parameter;
                                        const tooltip = required ? `(required) ${description}` : description;
                                        return (
                                            <InputHandle key={parameterName} id={parameterName} name={parameterName} isResource={true} tooltip={tooltip} />
                                        );
                                    }
                                })
                            }
                        </div>
                        <div className='outputs'>
                            {
                                outputs.map(output => <OutputHandle key={output} id={output} name={output} count={recordCount[output]} />)
                            }
                        </div>
                    </div>
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
                    <div className="widgets">
                        <Prompt nodeId={id} />
                    </div>
                    <ContentOverlay>
                        { tabs[tabShown]?.children }
                    </ContentOverlay>
                </div>

                {/* {!isCollapsed && <Monitor quickViewData={quickViewData} logsData={logsData} />} */}
            </Card>
        </div>
    );
}

function ContentOverlay({ children }) {
    if (!children) {
        return null;
    }

    return (
        <div style={{width: '200px', height: '120px'}}>
            <div style={{background: 'white', top:0,  width: '100%', height: '100%', position: 'absolute', zIndex: 5, overflow: 'auto'}}>
                { children }
            </div>
        </div>

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
