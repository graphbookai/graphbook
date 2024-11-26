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
import { Node } from './NodeAPI';

const { Panel } = Collapse;
const { useToken } = theme;

type QuickViewEntry = {
    [key: string]: any;
};

export function Step({ id, data, selected }) {
    const { name, parameters, inputs, outputs, isCollapsed } = data;
    const requiresInput = inputs.length > 0;
    
    return (
        <Node
            id={id}
            name={name}
            requiresInput={requiresInput}
            parameters={parameters}
            outputs={outputs}
            selected={selected}
            isCollapsed={isCollapsed}
            tabs={{}}
        />
    )
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
