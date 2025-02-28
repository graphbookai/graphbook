import React, { CSSProperties, useMemo } from 'react';
import { Image, Space, Flex } from 'antd';
import { theme } from 'antd';
import { useSettings } from '../../../hooks/Settings';
import { getMediaPath } from '../../../utils';
import type { ImageRef } from '../../../utils';
import ReactJson from '@microlink/react-json-view';

type QuickViewEntry = {
    [key: string]: any;
};

export function DataPreview({ data, showImages }: { data: QuickViewEntry, showImages: boolean }) {
    const globalTheme = theme.useToken().theme;

    if (!showImages) {
        return (
            <ReactJson
                style={{ maxHeight: '200px', overflow: 'auto', fontSize: '0.6em' }}
                theme={globalTheme.id === 0 ? "rjv-default" : "monokai"}
                name={false}
                displayDataTypes={false}
                indentWidth={2}
                src={data}
            />
        );
        
    }
    return (
        <EntryImages
            style={{ maxHeight: '200px', overflow: 'auto' }}
            entry={data}
        />
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
