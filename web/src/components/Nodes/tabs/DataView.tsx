import React from 'react';
import { Flex, Typography, theme } from 'antd';
import ReactJson from '@microlink/react-json-view';
import { EmptyTab } from './Empty';

const { Text } = Typography;

export type QuickViewEntry = {
    [key: string]: any;
}

export function DataView({ data }) {
    const globalTheme = theme.useToken().theme;
    const values = Object.entries<QuickViewEntry>(data).sort((a, b) => a[0].localeCompare(b[0]));

    if (values.length === 0) {
        return <EmptyTab />;
    }

    if (values.length === 1) {
        const [_, value] = values[0];
        return (
            <Data src={value} themeId={globalTheme.id} />
        );
    }

    return (
        <Flex vertical>
            {
                values.map(([key, value]) => {
                    return (
                        <Flex key={key} vertical>
                            <Text style={{ fontSize: '.6em', fontWeight: 'bold' }}>{key}</Text>
                            <Data src={value} themeId={globalTheme.id} />
                        </Flex>
                    );
                })
            }
        </Flex>
    );
}

function Data({ src, themeId }) {
    if (typeof(src) === 'object') {
        return (
            <ReactJson
                style={{ fontSize: '0.6em' }}
                theme={themeId === 0 ? "rjv-default" : "monokai"}
                name={false}
                displayDataTypes={false}
                indentWidth={2}
                src={src}
            />
        );
    }

    return (
        <pre style={{ fontSize: '0.6em' }}>{src}</pre>
    );
}
