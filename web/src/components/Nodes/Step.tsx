import React, { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import { Flex, Image, theme, Typography, Space } from 'antd';
import { useAPINodeMessageEffect, useLogSubscription } from '../../hooks/API';
import { useFilename } from '../../hooks/Filename';
import { getMediaPath } from '../../utils';
import { useSettings } from '../../hooks/Settings';
import { usePrompt, Prompt } from '../../hooks/Prompts';
import type { LogEntry, ImageRef } from '../../utils';
import { Node } from './Node';
import Icon, {
    PictureOutlined,
    FileTextOutlined,
    LeftOutlined,
    RightOutlined,
    DownloadOutlined,
    SwapOutlined,
    RotateLeftOutlined,
    RotateRightOutlined,
    ZoomOutOutlined,
    ZoomInOutlined
} from '@ant-design/icons';
import { Prompt as PromptWidget } from './widgets/Prompts';
import { Braces, Click } from '../../svg';
import { DataView, QuickViewEntry } from './tabs/DataView';
import { LogsView } from './tabs/LogsView';
import { EmptyTab } from './tabs/Empty';

const { Text } = Typography;

export function Step({ id, data, selected }) {
    const { name, parameters, inputs, outputs, isCollapsed } = data;
    const [quickViewData, setQuickViewData] = useState<QuickViewEntry>({});
    const [errored, setErrored] = useState<boolean>(false);
    const [recordCount, setRecordCount] = useState({});
    const [isPromptNode, setIsPromptNode] = useState(false);
    const [prompt, setPrompt] = useState<Prompt | null>(null);
    const filename = useFilename();

    useAPINodeMessageEffect('view', id, filename, (msg) => {
        setQuickViewData(msg);
    });

    const logsData = useLogSubscription(filename, id);

    useAPINodeMessageEffect('stats', id, filename, (msg) => {
        setRecordCount(msg.queue_size || {});
    });

    const setSubmitted = usePrompt(id, (prompt) => {
        setPrompt(prompt);
    });

    useEffect(() => {
        if (prompt && prompt.type !== null) {
            setIsPromptNode(true);
        }
    }, [prompt]);

    const tabs = useMemo(() => {
        const t = [{
            label: 'Data',
            children: <DataView data={quickViewData} />,
            icon: <Icon component={Braces} />
        }, {
            label: 'Images',
            children: <ImagesView data={quickViewData} />,
            icon: <PictureOutlined />
        }, {
            label: logsData.length === 0 ? 'Logs' : `Logs (${logsData.length})`,
            children: <LogsView data={logsData} />,
            icon: <FileTextOutlined />
        }];
        if (isPromptNode) {
            t.push({
                label: 'Prompts',
                children: <PromptView nodeId={id} prompt={prompt} setSubmitted={setSubmitted} />,
                icon: <Click />
            });
        }
        return t;
    }, [quickViewData, logsData, isPromptNode, prompt, setSubmitted]);

    useEffect(() => {
        for (const log of logsData) {
            if (log.type === 'error') {
                setErrored(true);
                return;
            }
        }

        setErrored(false);
    }, [logsData]);

    return (
        <Node
            id={id}
            name={name}
            inputs={inputs}
            parameters={parameters}
            outputs={outputs.map(o => ({ id: o, label: o, recordCount: recordCount[o] }))}
            selected={selected}
            errored={errored}
            isCollapsed={isCollapsed}
            tabs={tabs}
            defaultTab={data.properties?.defaultTab}
        />
    );
}

function ImagesView({ data }) {
    const values = Object.entries<QuickViewEntry>(data).sort((a, b) => a[0].localeCompare(b[0]));
    const [settings, _] = useSettings();
    const [currentImagePreview, setCurrentImagePreview] = useState('');

    const imageEntries = useMemo(() => {
        let entries: { [key: string]: ImageRef[] } = {};
        values.forEach(([outputKey, data]) => {
            Object.entries(data).forEach(([key, item]) => {
                let imageItems: any = [];
                if (Array.isArray(item)) {
                    imageItems = item.filter(item => item.type?.slice(0, 5) === 'image');
                } else {
                    if (item.type?.slice(0, 5) === 'image') {
                        imageItems.push(item);
                    }
                }
                if (imageItems.length > 0) {
                    entries[`${outputKey}/${key}`] = imageItems;
                }
            })
        });
        return entries;
    }, [values]);

    const onDownloadImage = useCallback(() => {
        const url = currentImagePreview;
        fetch(url)
            .then((response) => response.blob())
            .then((blob) => {
                const blobUrl = URL.createObjectURL(new Blob([blob]));
                const link = document.createElement('a');
                link.href = blobUrl;
                const { type } = blob;
                const filename = Date.now() + '.' + type.split('/')[1];
                link.download = filename;
                document.body.appendChild(link);
                link.click();
                URL.revokeObjectURL(blobUrl);
                link.remove();
            });
    }, [currentImagePreview]);

    return (
        Object.keys(imageEntries).length === 0 ?
            <EmptyTab description='No images' /> :
            Object.entries(imageEntries).map(([key, value]) => (
                <Flex vertical key={key}>
                    <Text style={{ fontSize: '.6em', fontWeight: 'bold' }}>{key}</Text>
                    <Flex>
                        {
                            value.map((image, i) => (
                                <Image
                                    key={i}
                                    src={getMediaPath(settings, image)}
                                    height={settings.quickviewImageHeight}
                                    preview={{
                                        onVisibleChange: (isVisible) => {
                                            if (isVisible) {
                                                setCurrentImagePreview(getMediaPath(settings, image));
                                            }
                                        },
                                        toolbarRender: (
                                            _,
                                            {
                                                transform: { scale },
                                                actions: {
                                                    onActive,
                                                    onFlipY,
                                                    onFlipX,
                                                    onRotateLeft,
                                                    onRotateRight,
                                                    onZoomOut,
                                                    onZoomIn,
                                                }
                                            }
                                        ) => (
                                            <Space size={12} className="toolbar-wrapper">
                                                <LeftOutlined onClick={() => onActive?.(-1)} />
                                                <RightOutlined onClick={() => onActive?.(1)} />
                                                <DownloadOutlined onClick={onDownloadImage} />
                                                <SwapOutlined rotate={90} onClick={onFlipY} />
                                                <SwapOutlined onClick={onFlipX} />
                                                <RotateLeftOutlined onClick={onRotateLeft} />
                                                <RotateRightOutlined onClick={onRotateRight} />
                                                <ZoomOutOutlined disabled={scale === 1} onClick={onZoomOut} />
                                                <ZoomInOutlined disabled={scale === 50} onClick={onZoomIn} />
                                            </Space>
                                        )
                                    }}
                                />
                            ))
                        }
                    </Flex>
                </Flex>
            ))
    );
}

function PromptView({ nodeId, prompt, setSubmitted }) {
    if (!prompt || prompt.type === null) {
        return <EmptyTab description='No prompts available' />;
    }

    return (
        <div className="widgets">
            <PromptWidget nodeId={nodeId} prompt={prompt} setSubmitted={setSubmitted} />
        </div>
    );
}
